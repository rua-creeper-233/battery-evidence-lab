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


def dataset_status(path: Path, fallback: dict | None = None) -> dict:
    if not path.exists():
        # A clean checkout intentionally has no local payloads. Preserve the
        # last published count/hash summary instead of replacing it with zeros.
        return dict(fallback) if fallback else {"rows": 0, "exists": False}
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
    previous_public = read_json(ROOT / "data/project_status.json", {})
    previous_datasets = previous_public.get("datasets", {})
    datasets = {label: dataset_status(ROOT / "finetune/data" / filename, previous_datasets.get(label)) for label, filename in
                (("train", "train.jsonl"), ("validation", "validation.jsonl"), ("test", "test.jsonl"))}
    smoke = smoke_status(smoke_output) if smoke_output else None
    static_qa = None
    research_knowledge = None
    paper_insights = None
    insights_path = ROOT / "data/paper_insights.json"
    if insights_path.exists():
        from validate_paper_insights import validate as validate_insights
        insights = read_json(insights_path, {})
        errors = validate_insights(insights, papers)
        if errors:
            raise ValueError("invalid structured paper insights: " + "; ".join(errors))
        records = insights["papers"]
        paper_insights = {"cards": len(records), "condition_cards": sum(bool(r["sections"].get("conditions")) for r in records.values())}
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
            "paper_insights": paper_insights,
            "training_smoke": smoke,
            "model_status": ("Five-step GPU pipeline smoke completed; no formal retraining or scientific accuracy evaluation."
                             if smoke else "Prepared QA datasets retained; no model retraining performed for this release."),
            "scope": "Counts refer to curated catalog and local evidence library; public site contains metadata, not PDFs or private Zotero keys."}


def render_status(status: dict) -> str:
    train, val, test = (status["datasets"][key]["rows"] for key in ("train", "validation", "test"))
    model_note = ("A five-step GPU pipeline smoke test completed; this is not a training run or scientific accuracy evaluation."
                  if status.get("training_smoke") else "No model retraining was performed for this release.")
    static_qa = status.get("static_qa")
    knowledge = status.get("research_knowledge")
    insights = status.get("paper_insights")
    static_note = (f"Static reading guide: {static_qa['catalog_papers']} papers and {static_qa['rows']} rows, built from public catalog metadata.\n\n"
                   if static_qa else "")
    if knowledge:
        static_note = (f"Research knowledge cards: {knowledge['cards']}; references {knowledge['reference_papers']} catalog papers.\n\n" + static_note)
    if insights:
        static_note = (f"Structured paper insights: {insights['cards']} cards, including {insights['condition_cards']} with conditions or hypotheses.\n\n" + static_note)
    hashes = " / ".join(f"{key}: {status['datasets'][key].get('sha256', 'unavailable')}" for key in ("train", "validation", "test"))
    return (f"# Project status\n\nAs of {status['as_of']}. Generated deterministically by `update_project_status.py`.\n\n"
            f"| Metric | Count |\n|---|---:|\n| Curated papers (unique DOI) | {status['papers']} |\n"
            f"| Papers from 2023 onward | {status['recent_2023_onward']} |\n| Web of Science records | {status['wos_records']} |\n"
            f"| Training rows | {train} |\n| Validation rows | {val} |\n| Test rows | {test} |\n\n"
            f"{static_note}"
            f"{model_note} Source-group splits keep a DOI and its connected records together.\n\n"
            f"Dataset SHA-256 (local payloads are not published): {hashes}.\n")


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
        model_note = ("A five-step GPU pipeline smoke test completed; no formal training or accuracy evaluation."
                      if status.get("training_smoke") else "No model retraining was performed for this release.")
        summary = (f"\nAs of **{status['as_of']}**: **{status['papers']} curated papers with unique DOIs**; "
                   f"Web of Science records: **{status['wos_records']}**.\n\n"
                   + (f"Static reading guide: **{status['static_qa']['rows']} rows / {status['static_qa']['catalog_papers']} papers**.\n\n" if status.get("static_qa") else "")
                   + (f"Research knowledge cards: **{status['research_knowledge']['cards']}**, with workflow and citation boundaries.\n\n" if status.get("research_knowledge") else "")
                   + (f"Structured paper insights: **{status['paper_insights']['cards']} cards**, including {status['paper_insights']['condition_cards']} with conditions or hypotheses.\n\n" if status.get("paper_insights") else "")
                   + f"Training data: **{rows['train']['rows']} train / {rows['validation']['rows']} validation / {rows['test']['rows']} test**. {model_note} See [project status](guides/PROJECT_STATUS.md) for counts and hashes; local payloads are not published.\n")
        path.write_text(prefix + start + summary + end + suffix, encoding="utf-8")
    print(json.dumps({key: status[key] for key in ("papers", "local_fulltext_papers", "indexed_chunks", "dataset_rows")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
