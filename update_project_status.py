"""Generate public release statistics from current files, without private keys."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE_STATUS = ROOT / "private" / "project_status.local.json"


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dataset_status(path: Path) -> dict:
    if not path.exists():
        return {"rows": 0, "exists": False}
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return {"rows": len(rows), "exists": True, "sha256": hashlib.sha256(raw).hexdigest(),
            "categories": dict(sorted(Counter(row.get("category", "unknown") for row in rows).items()))}


def smoke_status(output: Path) -> dict:
    output = output.resolve()
    if not output.is_relative_to((ROOT / "finetune/outputs").resolve()):
        raise ValueError("Smoke output must remain inside finetune/outputs")
    state = read_json(output / "trainer_state.json", {})
    if state.get("global_step") != 5 or state.get("max_steps") != 5:
        raise ValueError("Smoke validation requires a completed five-step run")
    for filename in ("adapter_config.json", "adapter_model.safetensors"):
        if not (output / filename).is_file() or (output / filename).stat().st_size == 0:
            raise ValueError(f"Missing smoke artifact: {filename}")
    return {"run_type": "five_step_pipeline_smoke_only", "global_step": 5,
            "output": output.relative_to(ROOT).as_posix(),
            "scientific_accuracy_evaluated": False}


def build_status(date: str, smoke_output: Path | None = None) -> dict:
    papers = read_json(ROOT / "data/papers.json", [])
    ids = {paper["id"] for paper in papers}
    dois = {str(paper.get("doi", "")).lower().strip() for paper in papers}
    if len(ids) != len(papers) or len(dois) != len(papers) or "" in dois:
        raise ValueError("The curated catalog must have unique nonempty IDs and DOIs")
    manifest = read_json(ROOT / "literature/manifest.json", {})
    fulltexts = []
    for pid, record in manifest.get("papers", {}).items():
        if pid not in ids or record.get("status") != "downloaded":
            continue
        relative = record.get("local_pdf", "")
        candidate = (ROOT / relative).resolve() if relative else None
        if candidate and candidate.is_relative_to(ROOT) and candidate.is_file() and record.get("validation", {}).get("valid_pdf"):
            fulltexts.append(pid)
    chunks_path = ROOT / "data/fulltext_chunks.jsonl"
    chunk_count = 0
    indexed_ids = set()
    if chunks_path.exists():
        with chunks_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    item = json.loads(line)
                    if item.get("paper_id") in ids:
                        chunk_count += 1
                        indexed_ids.add(item["paper_id"])
    tags = read_json(ROOT / "data/paper_tags.json", {})
    datasets = {label: dataset_status(ROOT / "finetune/data" / filename) for label, filename in
                (("train", "train.jsonl"), ("validation", "validation.jsonl"), ("test", "test.jsonl"))}
    smoke = smoke_status(smoke_output) if smoke_output else None
    static_qa = None
    research_knowledge = None
    knowledge_path = ROOT / "data/research_knowledge.json"
    if knowledge_path.exists():
        from validate_research_knowledge import validate as validate_knowledge
        knowledge = validate_knowledge(read_json(knowledge_path, {}), papers)
        research_knowledge = {"cards":len(knowledge['cards']),
                              "by_kind":dict(Counter(card['kind'] for card in knowledge['cards'])),
                              "reference_papers":len({source['paper_id'] for card in knowledge['cards'] for source in card['sources']})}
    static_qa_path = ROOT / "data/static_qa.json"
    if static_qa_path.exists():
        from build_static_qa import validate
        data = read_json(static_qa_path, {})
        validate(data, papers, read_json(ROOT / "data/learning_route.json", {}),
                 read_json(ROOT / "data/paper_titles_zh.json", {}))
        static_qa = {"catalog_papers": data["catalog_count"], "rows": data["qa_count"],
                     "evidence_level": "curated_metadata"}
    return {"schema_version": 1, "as_of": date, "papers": len(papers),
            "recent_2023_onward": sum(int(p.get("year", 0)) >= 2023 for p in papers),
            "publication_years": dict(sorted(Counter(str(p.get("year")) for p in papers).items())),
            "publication_types": dict(sorted(Counter(p.get("document_type", "Paper") for p in papers).items())),
            "wos_records": sum(bool(p.get("wos_uid")) for p in papers),
            "local_fulltext_papers": len(fulltexts), "local_fulltext_missing": len(papers) - len(fulltexts),
            "indexed_papers": len(indexed_ids), "indexed_chunks": chunk_count,
            "tags": tags.get("counts", {}), "datasets": datasets,
            "dataset_rows": sum(item["rows"] for item in datasets.values()),
            "static_qa": static_qa,
            "research_knowledge": research_knowledge,
            "training_smoke": smoke,
            "model_status": ("Five-step GPU pipeline smoke completed; no formal retraining or scientific accuracy evaluation."
                             if smoke else "Prepared QA datasets retained; no model retraining performed for this release."),
            "scope": "Counts refer to curated catalog and local evidence library; public site contains metadata, not PDFs or private Zotero keys."}


def render_status(status: dict) -> str:
    train, val, test = (status["datasets"][key]["rows"] for key in ("train", "validation", "test"))
    model_note = ("已完成 5 步 GPU 训练流程验证，仅确认训练与 adapter 保存可用；未做正式重新训练或科研准确率评估。"
                  if status.get("training_smoke") else "本版本未重新训练模型。")
    static_qa = status.get("static_qa")
    knowledge = status.get("research_knowledge")
    static_note = (f"静态导读：{static_qa['catalog_papers']} 篇论文 × 4 类，共 {static_qa['rows']} 条；"
                   "按公开目录整理研究主题、方法标签、范围与阅读路线。\n\n"
                   if static_qa else "")
    if knowledge:
        static_note = (f"专题科研问答：{knowledge['cards']} 个，分基础知识、计算流程和常见问题，引用 {knowledge['reference_papers']} 篇库内论文及官方文档，附操作步骤和验收项。\n\n" + static_note)
    return (f"# 当前项目状态\n\n统计日期：{status['as_of']}。由 `update_project_status.py` 根据实际库、索引与数据集生成。\n\n"
            f"| 项目 | 实际数量 |\n|---|---:|\n| 公开精选论文（唯一 DOI） | {status['papers']} |\n"
            f"| 2023 年及以后论文 | {status['recent_2023_onward']} |\n| 已有 WOS UT | {status['wos_records']} |\n"
            f"| QLoRA 训练样本 | {train} |\n| QLoRA 验证样本 | {val} |\n| QLoRA 测试样本 | {test} |\n\n"
            f"{static_note}"
            f"{model_note}训练/验证/测试按论文来源分组隔离；验证集用于选择方案，固定方案后再用测试集评估。\n\n"
            "网页发布书目、教学资料与汇总统计；论文正文和 Zotero 私有记录保存在本机。\n\n"
            "- [AI 实施指南](AI_BATTERY_APPLICATIONS.md)\n- [未来研究方向](BATTERY_COMPUTATION_FUTURE_DIRECTIONS.md)\n"
            "- JSON 统计：`data/project_status.json`；训练来源与文件 SHA-256：`finetune/data/manifest.json`。\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Release date YYYY-MM-DD in the user's timezone")
    parser.add_argument("--smoke-output", type=Path, help="Completed five-step adapter output; not a production model")
    args = parser.parse_args()
    status = build_status(args.date, args.smoke_output)
    PRIVATE_STATUS.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_status = {key: value for key, value in status.items() if key not in {
        "local_fulltext_papers", "local_fulltext_missing", "indexed_papers", "indexed_chunks"
    }}
    public_status["scope"] = "Counts refer to the curated catalog, educational metadata, and dataset rows; local full-text holdings and indexing remain private."
    (ROOT / "data/project_status.json").write_text(json.dumps(public_status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "guides/PROJECT_STATUS.md").write_text(render_status(public_status), encoding="utf-8")
    path = ROOT / "README.md"
    content = path.read_text(encoding="utf-8")
    start, end = "<!-- CURRENT_STATUS_START -->", "<!-- CURRENT_STATUS_END -->"
    if start in content and end in content:
        prefix, remaining = content.split(start, 1)
        _, suffix = remaining.split(end, 1)
        rows = status["datasets"]
        model_note = "已通过 5 步 GPU 流程验证，未做正式训练或准确率评估" if status.get("training_smoke") else "论文库、问答数据与模型分别维护，本版未重新训练"
        summary = (f"\n统计日期 **{status['as_of']}**：**{status['papers']} 篇唯一 DOI**；WOS UT **{status['wos_records']} 条**。\n\n"
                   + (f"静态导读：**{status['static_qa']['rows']} 条 / {status['static_qa']['catalog_papers']} 篇**，用于检索后的目录导读。\n\n" if status.get("static_qa") else "")
                   + (f"专题科研问答：**{status['research_knowledge']['cards']} 个**，包含基础知识、计算步骤、检查清单、常见问题与引用边界。\n\n" if status.get("research_knowledge") else "")
                   +
                   f"QLoRA 数据：**{rows['train']['rows']} 训练 / {rows['validation']['rows']} 验证 / {rows['test']['rows']} 测试**。{model_note}；数量与哈希详见 [当前状态](guides/PROJECT_STATUS.md)。\n")
        path.write_text(prefix + start + summary + end + suffix, encoding="utf-8")
    print(json.dumps({key: status[key] for key in ("papers", "local_fulltext_papers", "indexed_chunks", "dataset_rows")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
