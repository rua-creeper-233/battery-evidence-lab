import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import battery_lab.fetch_literature as fetch
from maintenance import audit_library, pull_zotero_fulltexts


TITLE = "Hybrid density functionals for semiconductor calculations"
BODY = " Abstract. We describe electronic energies and forces, compare independent calculations, and report convergence of the numerical results." * 5


def write_pdf(path, text):
    """Create a readable PDF fixture with real extractable text."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 20 750 Td ({escaped}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)


class FetchSafetyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="battery-fetch-test-")))
        self.pdf_dir = self.root / "literature/pdfs"
        self.pdf_dir.mkdir(parents=True)
        self.destination = self.pdf_dir / "paper.pdf"
        self.manifest = self.root / "literature/manifest.json"
        data = self.root / "data"
        data.mkdir()
        self.paper = {"id": "paper", "title": TITLE, "doi": "10.1000/test"}
        (data / "papers.json").write_text(json.dumps([self.paper]), encoding="utf-8")
        self.enterContext(patch.multiple(fetch, ROOT=self.root, PAPERS_PATH=data / "papers.json", MANIFEST_PATH=self.manifest,
            PDF_DIR=self.pdf_dir, QUARANTINE_DIR=self.root / "literature/quarantine", SUPPLEMENTARY_DIR=self.root / "literature/supplementary",
            TEXT_DIR=self.root / "literature/text", GLOBAL_INDEX=data / "fulltext_chunks.jsonl"))
        self.enterContext(patch.object(fetch, "candidate_sources", return_value=({}, [{"url": "https://example.invalid/article", "basis": "test"}])))

    def run_fetch(self, downloader, *options):
        with patch.object(fetch, "download_pdf", side_effect=downloader), patch.object(sys, "argv", ["fetch", "--paper-id", "paper", *options]):
            self.assertEqual(fetch.main(), 0)
        return json.loads(self.manifest.read_text(encoding="utf-8"))["papers"]["paper"]

    def download_text(self, text):
        def download(url, path):
            write_pdf(path, text)
            content = path.read_bytes()
            return {"ok": True, "final_url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        return download

    def test_invalid_existing_pdf_is_preserved_in_quarantine(self):
        original = b"%PDF-incomplete original copy"
        self.destination.write_bytes(original)
        result = self.run_fetch(lambda *_: {"ok": False}, "--skip-index")
        self.assertEqual((self.root / result["quarantined_pdf"]).read_bytes(), original)
        self.assertNotIn("local_pdf", result)
        self.assertEqual(result["status"], "not_downloaded")

    def test_failed_refresh_preserves_original_bytes_and_catalog_pointer(self):
        write_pdf(self.destination, TITLE + BODY)
        original = self.destination.read_bytes()
        prior = {"status": "downloaded", "local_pdf": "literature/pdfs/paper.pdf", "sha256": "previous", "bytes": len(original), "source_url": "previous-source"}
        self.manifest.write_text(json.dumps({"papers": {"paper": prior}}), encoding="utf-8")
        result = self.run_fetch(self.download_text("Unrelated botanical investigation" + BODY), "--refresh", "--skip-index")
        self.assertEqual(self.destination.read_bytes(), original)
        for key, value in prior.items():
            self.assertEqual(result[key], value)
        self.assertFalse(result["attempts"][0]["accepted_as_main_text"])
        self.assertEqual(list(self.pdf_dir.glob("*.candidate.pdf")), [])

    def test_metadata_only_never_moves_or_revalidates_existing_pdf(self):
        self.destination.write_bytes(b"unreadable original")
        prior = {"status": "downloaded", "local_pdf": "literature/pdfs/paper.pdf", "sha256": "previous"}
        self.manifest.write_text(json.dumps({"papers": {"paper": prior}}), encoding="utf-8")
        with patch.object(fetch, "validate_pdf", side_effect=AssertionError("PDF validation in metadata mode")):
            for extra in ([], ["--refresh"]):
                result = self.run_fetch(lambda *_: self.fail("Download in metadata mode"), "--metadata-only", "--skip-index", *extra)
                for key, value in prior.items():
                    self.assertEqual(result[key], value)
        self.assertEqual(self.destination.read_bytes(), b"unreadable original")
        self.assertFalse(fetch.QUARANTINE_DIR.exists())

    def test_parseable_wrong_article_and_thesis_are_never_indexed(self):
        for text in ("Unrelated botanical investigation" + BODY, "Doctoral dissertation. " + TITLE + BODY, "Presentation slides. " + TITLE + BODY):
            with self.subTest(text=text):
                result = self.run_fetch(self.download_text(text))
                self.assertEqual(result["status"], "not_downloaded")
                self.assertFalse(result["attempts"][0]["accepted_as_main_text"])
                self.assertFalse(self.destination.exists())
                self.assertEqual(fetch.GLOBAL_INDEX.read_text(encoding="utf-8"), "")
                self.assertEqual(list(self.pdf_dir.glob("*.candidate.pdf")), [])

    def test_correct_doi_less_article_is_downloaded_and_indexed(self):
        result = self.run_fetch(self.download_text(TITLE + BODY))
        self.assertTrue(result["attempts"][0]["accepted_as_main_text"])
        self.assertTrue(self.destination.is_file())
        chunks = [json.loads(line) for line in fetch.GLOBAL_INDEX.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(chunks)
        self.assertEqual({chunk["paper_id"] for chunk in chunks}, {"paper"})
        self.assertEqual(list(self.pdf_dir.glob("*.candidate.pdf")), [])

    def test_zotero_and_audit_use_the_same_article_identity_check(self):
        write_pdf(self.destination, "Unrelated botanical investigation" + BODY)
        validation = fetch.validate_pdf(self.destination, TITLE)
        self.assertTrue(validation["valid_pdf"])
        self.assertFalse(pull_zotero_fulltexts.is_matching_main_article(validation))
        self.paper["verification"] = {"doi": "verified_fixture"}
        self.manifest.write_text(json.dumps({"papers": {"paper": {"local_pdf": "literature/pdfs/paper.pdf"}}}), encoding="utf-8")
        with patch.multiple(audit_library, ROOT=self.root, PAPERS_PATH=fetch.PAPERS_PATH, MANIFEST_PATH=self.manifest), patch.object(audit_library, "load_json", side_effect=[[self.paper], json.loads(self.manifest.read_text())]), patch.object(audit_library, "save_json", side_effect=AssertionError("Rejected audit must not write")):
            with self.assertRaisesRegex(SystemExit, "manual identity review"):
                audit_library.main()

    def test_candidate_is_cleaned_if_replacement_fails(self):
        self.destination.write_bytes(b"original")
        with patch.object(Path, "replace", side_effect=PermissionError("destination in use")):
            with self.assertRaises(PermissionError):
                self.run_fetch(self.download_text(TITLE + BODY), "--refresh", "--skip-index")
        self.assertEqual(self.destination.read_bytes(), b"original")
        self.assertEqual(list(self.pdf_dir.glob("*.candidate.pdf*")), [])

    def test_candidate_and_partial_are_cleaned_on_interruption(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://example.invalid/article"
        response.headers = {"Content-Type": "application/pdf"}
        response.read.side_effect = [b"%PDF- partial content", KeyboardInterrupt()]
        with patch.object(fetch, "request", return_value=response):
            with self.assertRaises(KeyboardInterrupt):
                self.run_fetch(fetch.download_pdf, "--skip-index")
        self.assertEqual(list(self.pdf_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
