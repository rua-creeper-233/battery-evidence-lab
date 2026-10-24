"""Fail-closed validator for the optional public paper-insights dataset."""
from __future__ import annotations
import json, re, sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

TOP = {"schema_version", "as_of", "methodology", "papers"}
PAPER = {"paper_id", "doi", "sources", "sections", "relations"}
SOURCE = {"id", "url", "scope", "locator"}
ITEM = {"text", "source_refs", "kind"}
REL = {"subject", "predicate", "object", "source_refs", "kind"}
SECTIONS = {"research_question", "systems", "methods", "findings", "limits", "reproduction"}
SCOPES = {"abstract", "article", "author_code", "catalog"}
DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.I)

def _obj(value, label, errors):
    if not isinstance(value, dict): errors.append(f"{label}: expected object"); return False
    return True

def validate(data, papers=None):
    errors = []
    if not _obj(data, "root", errors): return errors
    unknown = set(data) - TOP
    if unknown: errors.append(f"root: unknown fields {sorted(unknown)}")
    if data.get("schema_version") != 1: errors.append("root.schema_version must be 1")
    if not isinstance(data.get("papers"), dict): errors.append("root.papers: expected object"); return errors
    methodology = data.get("methodology")
    if not isinstance(methodology, dict) or set(methodology) != {"reference_title", "reference_url", "implemented_layers", "note"}:
        errors.append("root.methodology: exact reference_title/reference_url/implemented_layers/note object required")
    elif (not all(isinstance(methodology[k], str) and methodology[k].strip() for k in methodology) or urlparse(methodology["reference_url"]).scheme != "https"):
        errors.append("root.methodology: nonempty strings and HTTPS reference_url required")
    if not isinstance(data.get("as_of"), str): errors.append("root.as_of: YYYY-MM-DD required")
    else:
        try: date.fromisoformat(data["as_of"])
        except ValueError: errors.append("root.as_of: YYYY-MM-DD required")
    catalog = {str(p.get("id")): p for p in (papers or []) if isinstance(p, dict) and p.get("id")}
    for key, paper in data["papers"].items():
        label = f"papers.{key}"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{1,127}", str(key)): errors.append(f"{label}: invalid canonical id")
        if not _obj(paper, label, errors): continue
        bad = set(paper) - PAPER
        if bad: errors.append(f"{label}: unknown fields {sorted(bad)}")
        if paper.get("paper_id") != key: errors.append(f"{label}.paper_id must match key")
        if catalog and key not in catalog: errors.append(f"{label}: unknown canonical catalog id")
        if catalog and key in catalog and paper.get("doi") and str(catalog[key].get("doi", "")).casefold() != str(paper["doi"]).casefold(): errors.append(f"{label}.doi: does not match catalog")
        if paper.get("doi") and not DOI.fullmatch(str(paper["doi"])): errors.append(f"{label}.doi: invalid DOI")
        sources = paper.get("sources")
        if not isinstance(sources, list) or not sources: errors.append(f"{label}.sources: non-empty list required"); sources = []
        ids = set()
        for i, source in enumerate(sources):
            sl = f"{label}.sources[{i}]"
            if not _obj(source, sl, errors): continue
            bad = set(source) - SOURCE
            if bad: errors.append(f"{sl}: unknown fields {sorted(bad)}")
            sid = source.get("id")
            if not isinstance(sid, str) or not sid or sid in ids: errors.append(f"{sl}.id: unique nonempty id required")
            else: ids.add(sid)
            parsed = urlparse(source.get("url", "") if isinstance(source.get("url"), str) else "")
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.hostname in {"localhost", "127.0.0.1", "::1"} or (parsed.hostname and (parsed.hostname.startswith("10.") or parsed.hostname.startswith("192.168.") or parsed.hostname.startswith("172."))): errors.append(f"{sl}.url: public HTTPS URL required")
            if source.get("scope") not in SCOPES: errors.append(f"{sl}.scope: invalid scope")
            if not isinstance(source.get("locator"), str) or not source["locator"].strip(): errors.append(f"{sl}.locator: nonempty required")
        sections = paper.get("sections", {})
        if not isinstance(sections, dict): errors.append(f"{label}.sections: expected object"); sections = {}
        bad = set(sections) - SECTIONS
        if bad: errors.append(f"{label}.sections: unknown fields {sorted(bad)}")
        for name, items in sections.items():
            if not isinstance(items, list): errors.append(f"{label}.sections.{name}: expected list"); continue
            for i, item in enumerate(items): _validate_claim(item, f"{label}.sections.{name}[{i}]", ids, errors)
        relations = paper.get("relations", [])
        if not isinstance(relations, list): errors.append(f"{label}.relations: expected list"); relations = []
        for i, item in enumerate(relations):
            if not _obj(item, f"{label}.relations[{i}]", errors): continue
            bad = set(item) - REL
            if bad: errors.append(f"{label}.relations[{i}]: unknown fields {sorted(bad)}")
            for field in ("subject", "predicate", "object"):
                if not isinstance(item.get(field), str) or not item[field].strip(): errors.append(f"{label}.relations[{i}].{field}: required")
            _validate_refs(item, f"{label}.relations[{i}]", ids, errors)
    return errors

def _validate_refs(item, label, ids, errors):
    refs = item.get("source_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in ids for ref in refs): errors.append(f"{label}.source_refs: must reference known sources")
    if item.get("kind") not in {"reported", "reading_guide"}: errors.append(f"{label}.kind: invalid")

def _validate_claim(item, label, ids, errors):
    if not _obj(item, label, errors): return
    bad = set(item) - ITEM
    if bad: errors.append(f"{label}: unknown fields {sorted(bad)}")
    if not isinstance(item.get("text"), str) or not item["text"].strip(): errors.append(f"{label}.text: required")
    elif re.fullmatch(r"(?:暂无|待补充|未知|n/a|tbd)[。.!！]?", item["text"].strip(), re.I): errors.append(f"{label}.text: boilerplate is not allowed")
    _validate_refs(item, label, ids, errors)

def main(argv=None):
    path = Path((argv or sys.argv[1:])[0]) if (argv or sys.argv[1:]) else Path("static/data/paper_insights.json")
    if not path.exists(): return 0
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: print(f"invalid JSON: {exc}", file=sys.stderr); return 1
    catalog = None
    catalog_path = path.parent / "papers.json"
    if catalog_path.exists():
        try:
            raw_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog = raw_catalog.get("papers", raw_catalog) if isinstance(raw_catalog, dict) else raw_catalog
        except Exception as exc: print(f"invalid catalog JSON: {exc}", file=sys.stderr); return 1
    errors = validate(data, catalog)
    for error in errors: print(error, file=sys.stderr)
    return 1 if errors else 0

if __name__ == "__main__": raise SystemExit(main())
