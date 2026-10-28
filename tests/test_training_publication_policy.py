import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from publication_safety import FORBIDDEN_PATH, scan_text
from training.expand_dataset import build, split
import update_project_status as status


class TrainingPublicationPolicyTests(unittest.TestCase):
    def test_payloads_and_manifests_are_forbidden_but_generators_are_allowed(self):
        for path in (
            "training/train.jsonl",
            "training/expanded_manifest.json",
            "finetune/data/validation.jsonl",
            "finetune/data/manifest.json",
        ):
            self.assertTrue(FORBIDDEN_PATH.search(path), path)
        for path in ("training/expand_dataset.py", "training/schema.json", "examples/qa.json"):
            self.assertFalse(FORBIDDEN_PATH.search(path), path)

    def test_insights_generate_scoped_doi_cited_guidance(self):
        paper = {"id": "p1", "doi": "10.1000/example", "title": "Example", "methods": ["MD"]}
        insights = {"p1": {"doi": "10.1000/example", "sources": [{"id": "d", "scope": "abstract", "locator": "page 1", "url": "https://doi.org/10.1000/example"}],
                           "sections": {"findings": [{"text": "A reported value.", "source_refs": ["d"], "kind": "reported"}],
                                         "reproduction": [{"text": "Run a smoke test.", "source_refs": ["d"], "kind": "reading_guide"}]}}}
        rows = build([paper], insights)
        insight_rows = [row for row in rows if row["category"] == "paper_insight"]
        self.assertEqual(len(insight_rows), 2)
        self.assertTrue(all("10.1000/example" in json.dumps(row, ensure_ascii=False) for row in insight_rows))
        serialized = json.dumps(insight_rows, ensure_ascii=False)
        self.assertIn("page 1", serialized)
        self.assertIn("https://doi.org/10.1000/example", serialized)
        self.assertIn("阅读建议，不是论文已报告结果", json.dumps(insight_rows[1], ensure_ascii=False))
        train, evaluation, test = split(insight_rows)
        self.assertEqual(len(train) + len(evaluation) + len(test), 2)
        self.assertEqual(len({row["split"] for row in insight_rows}), 1)

    def test_training_payload_text_is_not_public_scan_input(self):
        self.assertTrue(scan_text("{}", "finetune/data/train.jsonl") == [])
        self.assertTrue(FORBIDDEN_PATH.search("finetune/data/train.jsonl"))

    def test_clean_checkout_preserves_published_dataset_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/papers.json").write_text(json.dumps([{"id": "p1", "doi": "10.1000/p1"}]), encoding="utf-8")
            previous = {"datasets": {name: {"rows": 7, "exists": True, "sha256": f"hash-{name}"}
                                      for name in ("train", "validation", "test")}}
            (root / "data/project_status.json").write_text(json.dumps(previous), encoding="utf-8")
            with patch.object(status, "ROOT", root):
                result = status.build_status("2026-10-28")
            self.assertEqual(result["datasets"]["train"]["rows"], 7)
            self.assertEqual(result["datasets"]["test"]["sha256"], "hash-test")
            self.assertIn("Dataset SHA-256", status.render_status(result))

    def test_insight_records_never_cross_source_group_splits(self):
        papers = [{"id": "p1", "doi": "10.1000/p1", "title": "One"},
                  {"id": "p2", "doi": "10.1000/p2", "title": "Two"}]
        insights = {paper["id"]: {"doi": paper["doi"], "sources": [{"id": "d", "scope": "abstract"}],
                                   "sections": {"findings": [{"text": f"Finding {paper['id']}", "source_refs": ["d"]}]}}
                    for paper in papers}
        rows = build(papers, insights)
        train, evaluation, test = split(rows)
        assignments = {}
        for item in train + evaluation + test:
            for group in item["provenance"]["source_group_ids"]:
                assignments.setdefault(group, set()).add(item["split"])
        self.assertTrue(all(len(splits) == 1 for splits in assignments.values()))


if __name__ == "__main__":
    unittest.main()
