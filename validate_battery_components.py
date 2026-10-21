"""Validate the public battery-component reading map against canonical papers."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


COMPONENT_IDS = {"cathode", "anode", "electrolyte", "separator", "interface", "collectors"}
TOP_KEYS = {"schema_version", "as_of", "note", "sources", "components"}
COMPONENT_KEYS = {"id", "label", "label_en", "description", "scope", "papers"}
PAPER_KEYS = {"paper_id", "doi", "relation", "reason"}
SOURCE_HOSTS = {"energy.gov", "www.energy.gov", "anl.gov", "www.anl.gov", "publications.anl.gov"}


class ComponentValidationError(ValueError):
    """Invalid or stale public component map; never fill it with guessed papers."""


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise ComponentValidationError(f"{label}: unknown or missing fields")


def _text(value, label, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ComponentValidationError(f"{label}: expected nonempty text")


def validate(data, papers):
    _exact(data, TOP_KEYS, "component map")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ComponentValidationError("unsupported component schema")
    if not isinstance(data["as_of"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["as_of"]):
        raise ComponentValidationError("component map needs an update date")
    _text(data["note"], "map note")
    if not isinstance(papers, list):
        raise ComponentValidationError("canonical catalog must be a list")
    canonical = {}
    for paper in papers:
        if not isinstance(paper, dict) or not isinstance(paper.get("id"), str):
            raise ComponentValidationError("malformed canonical paper")
        if paper["id"] in canonical:
            raise ComponentValidationError("duplicate canonical paper ID")
        canonical[paper["id"]] = paper.get("doi")
    sources = data["sources"]
    if not isinstance(sources, list) or not sources:
        raise ComponentValidationError("figure needs a structural source")
    for source in sources:
        _exact(source, {"label", "url"}, "structural source")
        _text(source["label"], "source label", 300)
        _text(source["url"], "source URL", 1000)
        try:
            url = urlsplit(source["url"])
            allowed = (url.scheme == "https" and url.hostname in SOURCE_HOSTS
                       and url.port in (None, 443) and not url.username and not url.password
                       and not url.query and not url.fragment)
        except ValueError:
            allowed = False
        if not allowed:
            raise ComponentValidationError("figure source must be an allowed public primary URL")
    components = data["components"]
    if not isinstance(components, list) or len(components) != len(COMPONENT_IDS):
        raise ComponentValidationError("expected the six battery components")
    seen = set()
    for component in components:
        _exact(component, COMPONENT_KEYS, "component")
        cid = component["id"]
        if not isinstance(cid, str) or cid not in COMPONENT_IDS or cid in seen:
            raise ComponentValidationError("unknown or duplicate component ID")
        seen.add(cid)
        for field in ("label", "label_en", "description", "scope"):
            _text(component[field], field)
        rows = component["papers"]
        if not isinstance(rows, list):
            raise ComponentValidationError("component papers must be a list; empty is permitted")
        paper_ids = set()
        for row in rows:
            _exact(row, PAPER_KEYS, "component reference")
            _text(row["paper_id"], "paper_id", 300)
            _text(row["doi"], "DOI", 500)
            if row["paper_id"] in paper_ids or canonical.get(row["paper_id"]) != row["doi"]:
                raise ComponentValidationError("duplicate, unknown or stale component citation")
            paper_ids.add(row["paper_id"])
            if row["relation"] not in ("direct", "related"):
                raise ComponentValidationError("reference relation must be explicit")
            _text(row["reason"], "reference reason")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, nargs="?", default=Path(__file__).parent / "data/battery_components.json")
    args = parser.parse_args()
    root = Path(__file__).parent
    data = validate(json.loads(args.dataset.read_text(encoding="utf-8")),
                    json.loads((root / "data/papers.json").read_text(encoding="utf-8")))
    refs = [row for component in data["components"] for row in component["papers"]]
    print(json.dumps({"components": len(data["components"]), "cross_references": len(refs),
                      "unique_papers": len({row["paper_id"] for row in refs})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
