from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from battery_lab.agent import BatteryResearchAgent  # noqa: E402


class FulltextDoiLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="battery-doi-test-")
        root = Path(self.tempdir.name)
        self.data_path = root / "papers.json"
        self.fulltext_path = root / "fulltext.jsonl"
        papers = [
            {"id": "author_preprint", "title": "Author preprint", "doi": "10.1234/author.preprint", "year": 2025},
            {"id": "second_preprint", "title": "Second preprint", "doi": "10.1234/second.preprint", "year": 2025},
            {"id": "unrelated", "title": "Unrelated paper", "doi": "10.1234/unrelated", "year": 2024},
            {"id": "missing_row_doi", "title": "Missing row DOI", "doi": "10.1234/missing.row", "year": 2025},
        ]
        rows = [
            {
                "paper_id": "author_preprint", "doi": "10.1234/author.preprint",
                "page": 1, "chunk": 1, "section": "body",
                "text": "Abstract and methods for a sodium battery preprint without an identifier.",
            },
            {
                "paper_id": "author_preprint", "doi": "10.1234/author.preprint",
                "page": 4, "chunk": 2, "section": "references",
                "text": "References include 10.1234/second.preprint.",
            },
            {
                "paper_id": "author_preprint", "doi": "10.1234/second.preprint",
                "page": 5, "chunk": 3, "section": "body",
                "text": "A contradictory imported chunk carrying another paper DOI.",
            },
            {
                "paper_id": "second_preprint", "doi": "10.1234/second.preprint",
                "page": 2, "chunk": 1, "section": "body",
                "text": "Diffusion barrier and ionic transport results.",
            },
            {
                "paper_id": "unrelated", "doi": "10.1234/unrelated",
                "page": 1, "chunk": 1, "section": "body",
                "text": "This unrelated article cites 10.1234/author.preprint.",
            },
            {
                "paper_id": "missing_row_doi",
                "page": 1, "chunk": 1, "section": "body",
                "text": "Metadata identifies this preprint; the extracted body has no DOI.",
            },
        ]
        self.data_path.write_text(json.dumps(papers), encoding="utf-8")
        self.fulltext_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        self.agent = BatteryResearchAgent(
            data_path=self.data_path,
            fulltext_path=self.fulltext_path,
            extra_data_path=None,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_doi_uses_metadata_when_pdf_text_has_no_doi(self) -> None:
        hits = self.agent.search_fulltext("https://doi.org/10.1234/AUTHOR.PREPRINT.")
        self.assertEqual([hit["paper_id"] for hit in hits], ["author_preprint"])
        self.assertEqual(hits[0]["page"], 1)

    def test_reference_mention_does_not_match_unrelated_paper(self) -> None:
        hits = self.agent.search_fulltext("10.1234/author.preprint")
        self.assertEqual({hit["paper_id"] for hit in hits}, {"author_preprint"})

    def test_conflicting_chunk_doi_cannot_override_catalog_owner(self) -> None:
        hits = self.agent.search_fulltext("10.1234/second.preprint")
        self.assertNotIn("author_preprint", {hit["paper_id"] for hit in hits})

    def test_missing_chunk_doi_is_filled_from_catalog_owner(self) -> None:
        hits = self.agent.search_fulltext("10.1234/missing.row")
        self.assertEqual([hit["paper_id"] for hit in hits], ["missing_row_doi"])
        self.assertEqual(hits[0]["doi"], "10.1234/missing.row")

    def test_unknown_and_prefix_doi_return_no_hits(self) -> None:
        self.assertEqual(self.agent.search_fulltext("10.1234"), [])
        self.assertEqual(self.agent.search_fulltext("10.9999/does-not-exist"), [])

    def test_multiple_exact_dois_are_supported(self) -> None:
        hits = self.agent.search_fulltext("10.1234/author.preprint, 10.1234/second.preprint")
        self.assertEqual({hit["paper_id"] for hit in hits}, {"author_preprint", "second_preprint"})

    def test_topical_fulltext_search_remains_lexical(self) -> None:
        hits = self.agent.search_fulltext("diffusion barrier")
        self.assertEqual(hits[0]["paper_id"], "second_preprint")


if __name__ == "__main__":
    unittest.main()
