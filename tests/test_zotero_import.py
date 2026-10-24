from __future__ import annotations

import json
import tempfile
import unittest
from inspect import signature
from pathlib import Path
from unittest.mock import patch

from import_zotero_library import (
    COMMON_TAG,
    build_zotero_item,
    normalize_doi,
    save_new_item_with_optional_pdf,
)


class ZoteroImportTests(unittest.TestCase):
    def test_personal_import_report_stays_private_and_creates_parent(self) -> None:
        import import_zotero_library as module
        self.assertEqual(module.REPORT_PATH.parent, module.ROOT / "private")
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "private" / "audit.md"
            with patch.object(module, "REPORT_PATH", report):
                module.write_report([], {}, {})
            self.assertTrue(report.is_file())

    def test_normalize_doi(self) -> None:
        self.assertEqual(
            normalize_doi("https://doi.org/10.1038/S43588-022-00349-3."),
            "10.1038/s43588-022-00349-3",
        )

    def test_build_item_keeps_wos_and_project_tag(self) -> None:
        paper = {
            "title": "A paper",
            "authors": ["M. K. Aydinol", "Ceder, Gerbrand"],
            "summary": "Summary",
            "journal": "Journal",
            "year": 2024,
            "doi": "10.1000/test",
            "url": "https://doi.org/10.1000/test",
            "wos_uid": "WOS:123",
            "tags_zh": ["电池"],
        }
        item = build_zotero_item(paper, "connector-id")
        self.assertEqual(item["itemType"], "journalArticle")
        self.assertEqual(item["creators"][0]["lastName"], "Aydinol")
        self.assertEqual(item["creators"][1]["lastName"], "Ceder")
        self.assertIn("WOS:123", item["extra"])
        self.assertNotIn("2026-09-13", item["extra"])
        self.assertTrue(item["abstractNote"].startswith("Lab 导读（非原摘要）："))
        self.assertIn(COMMON_TAG, {tag["tag"] for tag in item["tags"]})

    def test_build_item_preserves_journal_details_and_supplied_verification_date(self) -> None:
        paper = {
            "title": "A paper",
            "abstract": "Original publisher abstract.",
            "journal": "Journal",
            "volume": "12",
            "issue": "3",
            "pages": "101-110",
            "year": 2024,
            "doi": "10.1000/test",
            "verification": {"verified_at": "2026-10-18"},
        }
        item = build_zotero_item(paper, "connector-id")
        self.assertEqual(item["abstractNote"], "Original publisher abstract.")
        self.assertEqual(item["volume"], "12")
        self.assertEqual(item["issue"], "3")
        self.assertEqual(item["pages"], "101-110")
        self.assertIn("verified 2026-10-18", item["extra"])

    def test_build_item_uses_article_number_when_pages_are_missing(self) -> None:
        paper = {
            "title": "An article-number paper",
            "journal": "Journal",
            "year": 2024,
            "doi": "10.1000/article-number",
            "article_number": "e12345",
        }
        item = build_zotero_item(paper, "connector-id")
        self.assertEqual(item["pages"], "e12345")

    def test_build_item_uses_canonical_multipart_author_details(self) -> None:
        paper = {
            "title": "A paper",
            "authors": ["Umberto   Dal Corso", "Giovanni  Di Marco"],
            "author_details": [
                {"given": "Umberto", "family": "Dal Corso"},
                {"given": "Giovanni", "family": "Di Marco"},
            ],
            "doi": "10.1000/authors",
        }
        item = build_zotero_item(paper, "connector-id")
        self.assertEqual(item["creators"][0]["lastName"], "Dal Corso")
        self.assertEqual(item["creators"][1]["lastName"], "Di Marco")

    def test_build_item_rejects_mismatched_author_details(self) -> None:
        paper = {
            "title": "A paper",
            "authors": ["Umberto Dal Corso"],
            "author_details": [{"given": "Umberto", "family": "Corso"}],
            "doi": "10.1000/authors",
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_zotero_item(paper, "connector-id")

    def test_attachment_title_is_optional_and_keyword_only(self) -> None:
        params = signature(save_new_item_with_optional_pdf).parameters
        self.assertIsNone(params["attachment_title"].default)
        self.assertEqual(params["attachment_title"].kind, params["attachment_title"].KEYWORD_ONLY)

    @patch("import_zotero_library._request")
    def test_attachment_title_is_used_when_supplied(self, request) -> None:
        request.return_value = (200, b"", {})
        paper = {"title": "A paper", "doi": "10.1000/test"}
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-test")
            save_new_item_with_optional_pdf(
                paper,
                pdf_path,
                attachment_title="Author manuscript PDF",
            )
        attachment_call = request.call_args_list[1]
        metadata = json.loads(attachment_call.kwargs["headers"]["X-Metadata"])
        self.assertEqual(metadata["title"], "Author manuscript PDF")

    def test_build_item_does_not_invent_verification_date(self) -> None:
        paper = {
            "title": "A paper",
            "journal": "Journal",
            "year": 2024,
            "doi": "10.1000/test",
        }
        item = build_zotero_item(paper, "connector-id")
        self.assertNotIn("2026-09-13", item["extra"])
        self.assertEqual(item["extra"], "Evidence status: DOI and publisher record verified; WOS not checked")

    def test_non_wos_paper_is_not_mislabeled(self) -> None:
        paper = {
            "title": "A DOI-verified starter paper",
            "authors": ["Alex Example"],
            "summary": "Summary",
            "journal": "Journal",
            "year": 2025,
            "doi": "10.1000/starter",
            "url": "https://doi.org/10.1000/starter",
            "tags_zh": ["入门"],
        }
        item = build_zotero_item(paper, "connector-id")
        tags = {tag["tag"] for tag in item["tags"]}
        self.assertIn("DOI-publisher-verified", tags)
        self.assertNotIn("WOS-verified", tags)
        self.assertIn("WOS not checked", item["extra"])


if __name__ == "__main__":
    unittest.main()
