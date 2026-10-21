"""Strict validation for the curated research-knowledge cards."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


class KnowledgeValidationError(ValueError):
    """Raised when a knowledge-card dataset is not safe to publish."""


TOP_KEYS = {"schema_version", "as_of", "cards"}
CARD_KEYS = {"id", "kind", "question", "aliases", "all_of", "answer", "steps", "checks", "boundary", "sources", "documentation", "tags"}
SOURCE_KEYS = {"paper_id", "doi", "locator", "note"}
DOC_KEYS = {"label", "url", "locator"}
KINDS = {"foundation", "workflow", "faq"}
DOC_HOSTS = {"vasp.at", "www.vasp.at/wiki", "vaspkit.com", "docs.lammps.org", "ase-lib.org", "docs.ase-lib.org", "pymatgen.org", "docs.deepmodeling.com", "docs.materialsproject.org"}


def _text(value: Any, name: str, *, max_len: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise KnowledgeValidationError(f"{name} must be nonempty text")
    return value


def _exact(obj: Any, keys: set[str], name: str) -> None:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise KnowledgeValidationError(f"{name} has unknown or missing keys")


def validate(dataset: Any, papers: Any) -> dict:
    """Validate and return *dataset*; no mutation or catalog-wide coverage is required."""
    _exact(dataset, TOP_KEYS, "dataset")
    if dataset["schema_version"] != 1 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(dataset["as_of"])):
        raise KnowledgeValidationError("unsupported schema or as_of")
    if not isinstance(papers, list):
        raise KnowledgeValidationError("papers must be a list")
    canonical: dict[str, str] = {}
    dois: set[str] = set()
    for paper in papers:
        if not isinstance(paper, dict) or not isinstance(paper.get("id"), str) or not isinstance(paper.get("doi"), str):
            continue
        if paper["id"].strip() and paper["doi"].strip() and paper["id"] not in canonical and paper["doi"] not in dois:
            canonical[paper["id"]] = paper["doi"]
            dois.add(paper["doi"])
        elif paper.get("id") in canonical or paper.get("doi") in dois:
            raise KnowledgeValidationError("papers must have unique canonical IDs and DOIs")
    cards = dataset["cards"]
    if not isinstance(cards, list) or not cards:
        raise KnowledgeValidationError("cards must be nonempty")
    ids: set[str] = set()
    for i, card in enumerate(cards):
        _exact(card, CARD_KEYS, f"card {i}")
        cid = _text(card["id"], "card id", max_len=200)
        if cid in ids:
            raise KnowledgeValidationError("duplicate card id")
        ids.add(cid)
        if card["kind"] not in KINDS:
            raise KnowledgeValidationError("invalid card kind")
        _text(card["question"], "question")
        aliases = card["aliases"]
        if not isinstance(aliases, list) or not 2 <= len(aliases) <= 4 or any(not isinstance(x, str) or not x.strip() or len(x) > 500 for x in aliases):
            raise KnowledgeValidationError("aliases must contain 2-4 nonempty strings")
        groups = card["all_of"]
        if not isinstance(groups, list) or not groups or any(not isinstance(g, list) or not g or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in g) for g in groups):
            raise KnowledgeValidationError("all_of must contain nonempty trigger groups")
        _text(card["answer"], "answer")
        for field in ("boundary",):
            _text(card[field], field)
        for field in ("steps", "checks"):
            value = card[field]
            if not isinstance(value, list) or not 1 <= len(value) <= 20 or any(not isinstance(x, str) or not x.strip() or len(x) > 1000 for x in value):
                raise KnowledgeValidationError(f"{field} must contain 1-20 nonempty strings")
        if not isinstance(card["tags"], list) or not 1 <= len(card["tags"]) <= 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 100 for x in card["tags"]):
            raise KnowledgeValidationError("tags must contain nonempty strings")
        sources = card["sources"]
        if not isinstance(sources, list) or not sources:
            raise KnowledgeValidationError("each card needs a paper source")
        for source in sources:
            _exact(source, SOURCE_KEYS, "source")
            pid = _text(source["paper_id"], "source paper_id", max_len=300)
            doi = _text(source["doi"], "source doi", max_len=500)
            if pid not in canonical or canonical[pid] != doi:
                raise KnowledgeValidationError("source citation is not canonical")
            _text(source["locator"], "source locator", max_len=1000)
            _text(source["note"], "source note", max_len=2000)
        docs = card["documentation"]
        if not isinstance(docs, list):
            raise KnowledgeValidationError("documentation must be a list")
        for doc in docs:
            _exact(doc, DOC_KEYS, "documentation")
            _text(doc["label"], "documentation label", max_len=500)
            url = _text(doc["url"], "documentation url", max_len=2000)
            match = re.fullmatch(r"https://([^/]+)(/.*)?", url, re.IGNORECASE)
            host_path = (match.group(1).lower() + (match.group(2) or "")).rstrip("/") if match else ""
            if not match or not any(host_path == host or host_path.startswith(host + "/") for host in DOC_HOSTS):
                raise KnowledgeValidationError("documentation URL is not an allowed primary source")
            _text(doc["locator"], "documentation locator", max_len=1000)
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("papers", type=Path, nargs="?", default=Path(__file__).parent / "data" / "papers.json")
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    papers = json.loads(args.papers.read_text(encoding="utf-8"))
    validate(data, papers)
    print(json.dumps({"cards": len(data["cards"]), "schema_version": data["schema_version"], "as_of": data["as_of"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
