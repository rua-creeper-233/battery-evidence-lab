import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from publication_safety import (
    PublicationSafetyError,
    assert_clean,
    sanitize_method_evidence,
    scan_text,
    validate_public_zotero_map,
)


class PublicationSafetyTests(unittest.TestCase):
    @staticmethod
    def _png_bytes(*, metadata=False, trailing=b"", dimensions=(1200, 630)):
        def chunk(kind, payload):
            raw = kind + payload
            return struct.pack(">I", len(payload)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", *dimensions, 8, 2, 0, 0, 0)
        chunks = [chunk(b"IHDR", ihdr)]
        if metadata:
            chunks.append(chunk(b"tEXt", b"generated=fixture"))
        chunks += [chunk(b"IDAT", b"fixture"), chunk(b"IEND", b"")]
        return b"\x89PNG\r\n\x1a\n" + b"".join(chunks) + trailing

    def test_generated_share_card_png_is_validated(self):
        from publication_safety import scan_files
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(scan_files([root / "static" / "share-card.png"], root), [])

    def test_share_card_png_rejects_metadata_trailing_and_wrong_size(self):
        from publication_safety import PublicationSafetyError, scan_files
        cases = (self._png_bytes(metadata=True), self._png_bytes(trailing=b"junk"), self._png_bytes(dimensions=(1, 1)))
        for payload in cases:
            with self.subTest(payload=payload[:24]):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    target = root / "docs" / "share-card.png"
                    target.parent.mkdir()
                    target.write_bytes(payload)
                    with self.assertRaises(PublicationSafetyError):
                        scan_files([target], root)

    def test_arbitrary_binary_inputs_still_fail_closed(self):
        from publication_safety import PublicationSafetyError, scan_files
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "static" / "other.bin"
            target.parent.mkdir()
            target.write_bytes(b"not a publication text file")
            from publication_safety import assert_clean
            self.assertRaises(PublicationSafetyError, assert_clean, scan_files([target], root))
            target = root / "static" / "other.dat"
            target.write_bytes(b"\xff\xfe")
            with self.assertRaises(PublicationSafetyError):
                scan_files([target], root)
            target = root / "static" / "share-card.png"
            target.write_bytes(b"not a PNG")
            with self.assertRaises(PublicationSafetyError):
                scan_files([target], root)

    def test_zotero_allowlist_is_empty(self):
        self.assertEqual(validate_public_zotero_map({"visibility": "public_sanitized", "items": {}})["items"], {})
        for value in (
            {"visibility": "public_sanitized", "items": {"paper": {"item_key": "abc"}}},
            {"visibility": "public", "items": {}},
            {"visibility": "public_sanitized", "items": {}, "extra": 1},
        ):
            with self.assertRaises(PublicationSafetyError):
                validate_public_zotero_map(value)

    def test_method_payload_is_empty_and_has_no_local_fields(self):
        public = sanitize_method_evidence({"generated_at": "2026-01-01T00:00:00Z", "papers": {"p": {
            "title": "Public author name", "doi": "10.1/x", "evidence": [{"signal": "MAE", "local_pdf_url": "/local-pdf/p.pdf", "page": 1}]
        }}})
        self.assertEqual(public["papers"], {})
        self.assertNotIn("generated_at", json.dumps(public))
        self.assertNotIn("local_pdf_url", json.dumps(public))

    def test_scanner_has_no_secret_snippets_and_accepts_placeholders(self):
        self.assertEqual(scan_text("Author: Jane Doe\npath=<project-root>\\data"), [])
        findings = scan_text("token=" + "AKIA" + "1234567890123456", "fixture.md")
        self.assertEqual([(x.path, x.line, x.type) for x in findings], [("fixture.md", 1, "credential_format")])
        with self.assertRaises(PublicationSafetyError) as raised:
            assert_clean(findings)
        self.assertNotIn("AKIA", str(raised.exception))

    def test_public_catalog_rejects_per_paper_fulltext_holdings(self):
        safe = '{"id":"paper-1","title":"Battery method","verification":{"publisher":"verified"}}'
        self.assertEqual(scan_text(safe, "data/papers.json"), [])
        private = json.dumps({"id": "paper-1", "verification": {"fulltext": "verified_local_pdf" + "_2026-10-14"}})
        findings = scan_text(private, "data/papers.json")
        self.assertTrue(any(item.type == "fulltext_verification" for item in findings))
        self.assertTrue(any(item.type == "private_evidence_value" for item in findings))

    def test_empty_fulltext_fields_are_allowed_only_as_empty_values(self):
        empty = '{"verification":{"fulltext":""}}'
        self.assertFalse(any(item.type == "private_evidence_value" for item in scan_text(empty, "data/papers.json")))

    def test_institution_session_marker_is_private_access_trace(self):
        marker = "verified_institution_session" + "_2026-09-13"
        findings = scan_text(json.dumps({"verification": {"wos": marker}}), "data/papers.json")
        self.assertTrue(any(item.type == "personal_access_trace" for item in findings))

    def test_empty_structured_fields_are_not_private_values(self):
        for value in (None, "", {}, []):
            content = json.dumps({"item_key": value}, indent=2)
            self.assertEqual(scan_text(content, "fixture.json"), [])
        self.assertTrue(scan_text(json.dumps({"item_key": "fixture-only"}), "fixture.json"))
        self.assertTrue(scan_text(json.dumps({"indexed_chunks": 1}), "fixture.json"))

    def test_private_paths_and_credential_shapes_are_redacted(self):
        from publication_safety import FORBIDDEN_PATH
        for path in (
            "data/fulltext_chunks.jsonl", "literature/manifest.json", "private/result.json", "model.gguf",
            ".env.backup", "data/zotero-links.local.json", "distill/cache.json", ".codex/state.json",
            ".agents/session.json", "private_backups/snapshot.zip", "backups/old.txt", "old_manifest.json",
            "local_auth/session.json", "local_logs/access.log",
        ):
            self.assertTrue(FORBIDDEN_PATH.search(path), path)
        for text in ("ghp_" + "a" * 36, "sk-proj-" + "a" * 24, "zotero://open-pdf/library/items/" + "ABC" + "12345", "C:/" + "Users/" + "example-user/file"):
            self.assertTrue(scan_text(text, "fixture.md"))

    def test_access_traces_and_authorization_codes_are_private(self):
        marker = "institution" + "_access_trace=2026-10-21"
        session = "specific" + "_user" + "_session=SESSION1234"
        authorized = "authorized" + "_download=2026-10-21"
        oauth_code = "oauth" + "_download" + "_code=CODE1234"
        text = "\n".join((marker, session, authorized, oauth_code))
        kinds = {item.type for item in scan_text(text, "fixture.md")}
        self.assertEqual(kinds, {"personal_access_trace", "download_authorization"})
        institution = "华南" + "师范大学" + "机构" + "会话"
        self.assertTrue(scan_text(institution, "fixture.md"))

    def test_structured_access_basis_is_private_but_public_affiliation_is_allowed(self):
        safe = json.dumps({"author": "Battery Materials Lab", "affiliation": "Example University"})
        self.assertEqual(scan_text(safe, "data/papers.json"), [])
        private = json.dumps({"verification": {"access_basis": "authorized institutional download"}})
        self.assertTrue(any(item.type == "private_evidence_value" for item in scan_text(private, "data/papers.json")))

    def test_build_rejects_bad_sources_before_any_docs_mutation(self):
        import shutil
        import build_pages
        import build_learning_route

        root = Path(__file__).resolve().parents[1]
        assets = (*build_pages.PAGE_NAMES, *build_pages.ASSET_NAMES)
        sources = [root / "static" / name for name in assets]
        sources += [root / "guides" / name for name in build_pages.GUIDE_NAMES]
        sources += [root / "FINETUNE_INTEGRATION.md", root / "static/data/zotero-links.json"]
        sources += [root / "examples/ai_battery" / name for name in ("relax_mace.py", "msd_from_csv.py", "example_trajectory.csv")]
        sources += [root / "data" / name for name in (*build_pages.DATA_NAMES, "method_evidence.auto.json")]
        for kind in ("zotero", "method", "catalog", "titles", "shared_asset", "domestic_asset", "domestic_registry", "domestic_private", "route", "guide"):
            with self.subTest(source=kind), tempfile.TemporaryDirectory() as folder:
                target_root = Path(folder)
                for source in sources:
                    target = target_root / source.relative_to(root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                target_docs = target_root / "docs"
                target_docs.mkdir()
                sentinel = target_docs / "sentinel.txt"
                sentinel.write_text("preserve existing publication", encoding="utf-8")
                if kind == "zotero":
                    target = target_root / "static/data/zotero-links.json"
                    value = {"visibility": "public_sanitized", "items": {"fixture": {}}}
                elif kind == "method":
                    target = target_root / "data/method_evidence.auto.json"
                    value = {"visibility": "public_sanitized", "papers": {"fixture": {}}}
                elif kind == "catalog":
                    target = target_root / "data/papers.json"
                    value = json.loads(target.read_text(encoding="utf-8"))
                    value[0]["title"] += " C:/" + "Users/" + "fixture-person/file"
                elif kind == "route":
                    target = target_root / "data/learning_route.json"
                    value = json.loads(target.read_text(encoding="utf-8"))
                    value["stages"][0]["summary"] += " sk-proj-" + "a" * 24
                elif kind == "titles":
                    target = target_root / "data/paper_titles_zh.json"
                    value = json.loads(target.read_text(encoding="utf-8"))
                    first = next(iter(value["papers"]))
                    value["papers"][first]["title"] += " C:/" + "Users/" + "fixture-person/file"
                elif kind == "shared_asset":
                    target = target_root / "static/lab-ui.js"
                    target.write_text("const leaked = 'sk-proj-" + "a" * 24 + "';", encoding="utf-8")
                    value = None
                elif kind == "domestic_asset":
                    target = target_root / "static/domestic-papers.js"
                    target.write_text("const leaked = 'sk-proj-" + "a" * 24 + "';", encoding="utf-8")
                    value = None
                elif kind == "domestic_registry":
                    target = target_root / "data/domestic_papers.json"
                    value = json.loads(target.read_text(encoding="utf-8"))
                    value["entries"][0]["topic"] = "unknown-topic"
                elif kind == "domestic_private":
                    target = target_root / "data/domestic_papers.json"
                    value = json.loads(target.read_text(encoding="utf-8"))
                    value["entries"][0]["private_path"] = "private/evidence.pdf"
                else:
                    target = target_root / "guides" / build_pages.GUIDE_NAMES[0]
                    target.write_text("contact=" + "fixture" + "@" + "example.invalid", encoding="utf-8")
                    value = None
                if value is not None:
                    target.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                with patch.object(build_pages, "ROOT", target_root), patch.object(build_pages, "DOCS", target_docs), patch.object(build_learning_route, "ROUTE_PATH", target_root / "data/learning_route.json"), patch.object(build_learning_route, "PAPERS_PATH", target_root / "data/papers.json"):
                    with self.assertRaises((PublicationSafetyError, ValueError)):
                        build_pages.main()
                self.assertEqual(list(target_docs.iterdir()), [sentinel])
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve existing publication")
                self.assertFalse((target_root / "static/learning-route.html").exists())
                self.assertFalse((target_root / "static/domestic-papers.html").exists())


if __name__ == "__main__":
    unittest.main()
