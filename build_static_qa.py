"""Build the bounded, metadata-only static QA extension.

This deliberately reads only the public catalog, title translations and learning
route.  It never opens full text or invents experimental parameters.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPERS = ROOT / "data" / "papers.json"
TITLES = ROOT / "data" / "paper_titles_zh.json"
ROUTE = ROOT / "data" / "learning_route.json"
OUT = ROOT / "data" / "static_qa.json"
AS_OF = "2026-10-21"

GENERIC_ROLE = "面向电池电解液、固态电解质、正极/界面模拟的可复用计算文献。"
GENERIC_CROSSREF_PREFIX = "基于 Crossref 出版社元数据核验："
GENERIC_CROSSREF_SUFFIX = "摘要/正文参数仍需按来源逐项复核。"
GENERIC_RATIONALE = re.compile(
    r"^(?:作为综述地图、工具/协议或流程入口，先选一套小复现。|"
    r"作为机制或成熟方法的复现与对照，需要参数和统计验证。|"
    r"作为研究机会与方法局限的证据，先验证目标域和已有基线。)\s*"
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _doi_url(doi: str) -> str:
    return "https://doi.org/" + doi.strip()

def _maps(route_records, title_records):
    return ((route_records or {}).get("papers", route_records or {}),
            (title_records or {}).get("papers", title_records or {}))

def _fingerprint(papers, route, titles):
    rows = []
    for p in papers:
        pid = str(p["id"]); r = route.get(pid, {}); t = titles.get(pid, {})
        rows.append({"id": pid, "doi": str(p["doi"]), "title": str(p["title"]),
                     "title_zh": t.get("title_zh", ""), "role": p.get("role"),
                     "summary": p.get("summary"), "methods": p.get("methods"),
                     "scope_note": p.get("scope_note"), "stage": r.get("stage"),
                     "rationale": r.get("rationale")})
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _answer(kind, paper, route):
    role = paper.get("role") or ""
    if role == GENERIC_ROLE:
        role = ""
    summary = paper.get("summary") or ""
    summary_placeholder = (not summary or (summary.startswith(GENERIC_CROSSREF_PREFIX) and summary.endswith(GENERIC_CROSSREF_SUFFIX)))
    if summary_placeholder:
        summary = "已登记书目，尚无内容摘录。"
    methods = paper.get("methods") or []
    scope = paper.get("scope_note") or "未提供范围说明。"
    method_text = "、".join(str(x) for x in methods) if methods else "目录未列出具体方法标签"
    r = route.get(str(paper["id"]), {}) if isinstance(route, dict) else {}
    stage = {"baseline": "baseline", "beginner": "入门", "intermediate": "进阶", "frontier": "前沿"}.get(r.get("stage"), "未分配路线阶段")
    rationale = GENERIC_RATIONALE.sub("", str(r.get("rationale", ""))).strip()
    if rationale.startswith("路线用途："):
        rationale = ""
    rationale = rationale or "未提供单独阅读理由。"
    if kind == "overview":
        if not role and summary_placeholder:
            return "已登记书目，尚无内容摘录。"
        parts = []
        if role:
            parts.append(f"目录定位：{role}")
        if summary:
            parts.append(f"元数据摘要：{summary}")
        return "。".join(parts) + ("。" if parts else "已登记书目，尚无内容摘录。")
    if kind == "methods":
        return f"目录列出的方法/工具标签：{method_text}。"
    if kind == "limitations":
        return f"范围提示：{scope}"
    return f"阅读路线：{stage}。理由：{rationale}"


def build(papers=None, route=None, title_records=None, *, as_of=AS_OF):
    papers = _read(PAPERS) if papers is None else papers
    title_records = _read(TITLES) if title_records is None else title_records
    route_records = _read(ROUTE) if route is None else route
    title_map = (title_records or {}).get("papers", title_records or {})
    route = (route_records or {}).get("papers", route_records or {})
    if not isinstance(papers, list) or len({p.get("id") for p in papers}) != len(papers):
        raise ValueError("catalog papers must have unique ids")
    entries = []
    kinds = (("overview", "这篇论文在目录中的定位和主题是什么？"),
             ("methods", "目录记录了哪些方法或工具？"),
             ("limitations", "从公开元数据看，这篇论文有哪些范围限制或需要核对之处？"),
             ("reading", "这篇论文在学习路线中应如何阅读，为什么？"))
    for paper in papers:
        pid, doi, title = str(paper["id"]), str(paper["doi"]), str(paper["title"])
        tr = title_map.get(pid, {})
        title_zh = tr.get("title_zh", "") if isinstance(tr, dict) else ""
        qids = []
        qas = []
        for suffix, question in kinds:
            qid = f"{pid}:{suffix}"
            qids.append(qid)
            fields = {"overview": ["role", "summary"], "methods": ["methods"],
                      "limitations": ["scope_note"], "reading": ["learning_route.stage", "learning_route.rationale"]}[suffix]
            qas.append({"id": qid, "intent": suffix, "question": question,
                        "answer": _answer(suffix, paper, route), "source_fields": fields,
                        "source_urls": [_doi_url(doi)]})
        entries.append({"paper_id": pid, "doi": doi, "title": title, "title_zh": title_zh,
                        "qa_ids": qids, "qas": qas})
    dataset = {"schema_version": 1, "as_of": as_of, "catalog_count": len(papers), "qa_count": len(papers) * 4,
               "catalog_fingerprint": _fingerprint(papers, route, title_map),
               "static_extension": True, "evidence_level": "curated_metadata",
               "entries": entries}
    validate(dataset, papers, route, title_records)
    return dataset


def validate(dataset, papers=None, route=None, title_records=None):
    if not isinstance(dataset, dict) or set(dataset) != {"schema_version", "as_of", "catalog_count", "qa_count", "catalog_fingerprint", "static_extension", "evidence_level", "entries"} or type(dataset.get("schema_version")) is not int or dataset["schema_version"] != 1 or dataset.get("static_extension") is not True or dataset.get("evidence_level") != "curated_metadata" or not isinstance(dataset.get("as_of"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dataset["as_of"]):
        raise ValueError("invalid static QA schema")
    date.fromisoformat(dataset["as_of"])
    if any(type(dataset.get(key)) is not int for key in ("catalog_count", "qa_count")):
        raise ValueError("static QA counts must be integers")
    if papers is None:
        papers = _read(PAPERS)
    if route is None: route = _read(ROUTE)
    if title_records is None: title_records = _read(TITLES)
    route, title_records = _maps(route, title_records)
    if (not isinstance(papers, list) or not papers
            or any(not isinstance(p, dict) or any(not isinstance(p.get(key), str) or not p[key].strip() for key in ("id", "doi", "title")) for p in papers)
            or len({p["id"] for p in papers}) != len(papers)):
        raise ValueError("invalid catalog")
    expected = {str(p["id"]): (str(p["doi"]), str(p["title"])) for p in papers}
    if dataset.get("catalog_count") != len(expected) or dataset.get("qa_count") != len(expected) * 4 or dataset.get("catalog_fingerprint") != _fingerprint(papers, route, title_records):
        raise ValueError("stale catalog fingerprint or counts")
    entries = dataset.get("entries")
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise ValueError("entries must cover catalog")
    seen = set(); qa_seen = set()
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError("invalid static QA entry")
        pid = e.get("paper_id")
        if pid in seen or pid not in expected or (e.get("doi"), e.get("title")) != expected[pid]:
            raise ValueError(f"stale or duplicate paper entry: {pid}")
        seen.add(pid)
        if (set(e) != {"paper_id", "doi", "title", "title_zh", "qa_ids", "qas"}
                or not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", e["doi"])
                or not isinstance(e["title_zh"], str)
                or not isinstance(e.get("qas"), list) or len(e["qas"]) != 4
                or any(not isinstance(q, dict) for q in e["qas"])
                or not isinstance(e.get("qa_ids"), list) or len(e["qa_ids"]) != 4
                or any(not isinstance(qid, str) for qid in e["qa_ids"])
                or set(e["qa_ids"]) != {q.get("id") for q in e["qas"]}):
            raise ValueError(f"paper {pid} must have four QAs")
        tr = title_records.get(pid, {})
        if tr.get("title") != e["title"] or tr.get("doi") != e["doi"] or tr.get("title_zh", "") != e.get("title_zh", ""):
            raise ValueError("title map disagrees with static QA dataset")
        p = next(x for x in papers if str(x["id"]) == pid)
        expected_questions = {"overview": "这篇论文在目录中的定位和主题是什么？", "methods": "目录记录了哪些方法或工具？", "limitations": "从公开元数据看，这篇论文有哪些范围限制或需要核对之处？", "reading": "这篇论文在学习路线中应如何阅读，为什么？"}
        expected_answers = dict((s, _answer(s, p, route)) for s in expected_questions)
        for qa in e["qas"]:
            if set(qa) != {"id", "intent", "question", "answer", "source_fields", "source_urls"} or qa.get("id") in qa_seen:
                raise ValueError("invalid QA provenance")
            if qa.get("id") != f"{pid}:{qa.get('intent')}" or qa.get("intent") not in expected_answers or qa.get("question") != expected_questions[qa["intent"]] or qa.get("answer") != expected_answers[qa["intent"]]: raise ValueError("stale or invented QA")
            expected_fields = {"overview": ["role", "summary"], "methods": ["methods"], "limitations": ["scope_note"], "reading": ["learning_route.stage", "learning_route.rationale"]}[qa["intent"]]
            if qa.get("source_fields") != expected_fields: raise ValueError("invalid source fields")
            qa_seen.add(qa["id"])
            allowed = {"role", "summary", "methods", "scope_note", "learning_route.stage", "learning_route.rationale"}
            if not set(qa.get("source_fields", [])) <= allowed:
                raise ValueError("unallowlisted source field")
            if qa.get("source_urls") != [_doi_url(e["doi"])] or not all(str(u).startswith("https://doi.org/") for u in qa.get("source_urls", [])):
                raise ValueError("unsafe or mismatched source URL")
    if seen != set(expected) or len(qa_seen) != len(expected) * 4 or len({e["doi"].lower() for e in entries}) != len(entries) or any(len({q["intent"] for q in e["qas"]}) != 4 for e in entries):
        raise ValueError("catalog/QA coverage mismatch")
    return True


if __name__ == "__main__":
    d = build()
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {OUT} ({d['catalog_count']} papers, {d['qa_count']} QAs)")
