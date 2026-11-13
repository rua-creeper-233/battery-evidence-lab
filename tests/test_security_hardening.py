"""Regression tests for the security hardening pass (2026-11-13)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library_store  # noqa: E402
from fetch_literature import _is_public_https_url, request  # noqa: E402
from publication_safety import FORBIDDEN_PATH, scan_text  # noqa: E402
from server import Handler  # noqa: E402


class _Config:
    public_api = True
    access_token = "test-access-token-123456"
    allowed_origins = {"https://rua-creeper-233.github.io"}
    server_address = ("127.0.0.1", 8765)


def make_handler(host: str, origin: str = "", authorization: str = "", **extra: str) -> Handler:
    handler = object.__new__(Handler)
    handler.server = _Config()
    handler.client_address = ("127.0.0.1", 50000)
    headers = Message()
    headers["Host"] = host
    if origin:
        headers["Origin"] = origin
    if authorization:
        headers["Authorization"] = authorization
    for key, value in extra.items():
        headers[key.replace("_", "-")] = value
    handler.headers = headers
    handler._json = lambda payload, status=200: setattr(handler, "response", (payload, status))
    return handler


def remote_post(path: str, body: dict) -> Handler:
    raw = json.dumps(body).encode()
    handler = make_handler("demo.trycloudflare.com", "https://rua-creeper-233.github.io",
                           "Bearer test-access-token-123456",
                           Content_Type="application/json", Content_Length=str(len(raw)))
    handler.path = path

    class _Body:
        def read(self, size):
            return raw[:size]
    handler.rfile = _Body()
    return handler


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[bool] = []
        self.papers = [{"id": "p1", "title": "T", "summary": "S"}]
        self.fulltext_chunks = [{"paper_id": "p1", "text": "private full text"}]

    def answer(self, question, limit=5, use_rag=True):
        self.calls.append(use_rag)
        return {
            "answer_markdown": "x",
            "fulltext_hits": [{"excerpt": "private"}],
            "rag": {"used": False, "source_provenance": {"S1": "p.3"}},
            "provenance": {"data_file": "C:/" + "Users/" + "someone/data.json", "fulltext_file": "C:/x", "fulltext_paper_count": 3,
                           "fulltext_chunk_count": 9, "paper_count": 1},
        }


class ServerTunnelTests(unittest.TestCase):
    def test_remote_chat_never_uses_rag_and_drops_workstation_fields(self) -> None:
        agent = FakeAgent()
        handler = remote_post("/api/chat", {"question": "q", "use_rag": True})
        with patch("server.AGENT", agent):
            handler.do_POST()
        payload, status = handler.response
        self.assertEqual(status, 200)
        self.assertEqual(agent.calls, [False])
        self.assertEqual(payload["fulltext_hits"], [])
        self.assertNotIn("source_provenance", payload["rag"])
        for key in ("data_file", "fulltext_file", "fulltext_paper_count", "fulltext_chunk_count"):
            self.assertNotIn(key, payload["provenance"])
        self.assertEqual(payload["provenance"]["paper_count"], 1)

    def test_remote_keywords_cannot_read_private_fulltext_by_paper_id(self) -> None:
        handler = remote_post("/api/keywords", {"paper_id": "p1"})
        with patch("server.AGENT", FakeAgent()):
            handler.do_POST()
        self.assertEqual(handler.response[1], 400)
        self.assertIn("paper_id", handler.response[0]["error"])

    def test_proxy_headers_mark_a_loopback_request_as_remote(self) -> None:
        self.assertTrue(make_handler("127.0.0.1:8765")._is_local_request())
        for header in ("Cf_Connecting_IP", "X_Forwarded_For", "Forwarded"):
            with self.subTest(header=header):
                self.assertFalse(make_handler("localhost:8765", **{header: "203.0.113.9"})._is_local_request())

    def test_other_localhost_dev_servers_are_not_trusted_origins(self) -> None:
        self.assertTrue(make_handler("127.0.0.1:8765", "http://127.0.0.1:8765")._is_local_request())
        other = make_handler("127.0.0.1:8765", "http://localhost:3000")
        self.assertFalse(other._is_local_request())
        self.assertFalse(other._origin_allowed())

    def test_json_endpoints_require_json_content_type(self) -> None:
        handler = remote_post("/api/chat", {"question": "q"})
        handler.headers.replace_header("Content-Type", "text/plain")
        with patch("server.AGENT", FakeAgent()):
            handler.do_POST()
        self.assertEqual(handler.response[1], 400)

    def test_handler_has_socket_timeout(self) -> None:
        self.assertGreater(Handler.timeout or 0, 0)


class LibraryStoreTests(unittest.TestCase):
    def test_damaged_library_file_is_not_treated_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            damaged = Path(folder) / "user-papers.local.json"
            damaged.write_text("[{\"id\": ", encoding="utf-8")
            with self.assertRaises(library_store.LibraryStateError):
                library_store._read_json(damaged, [])
            self.assertEqual(library_store._read_json(Path(folder) / "absent.json", []), [])

    def _ingest(self, folder: Path, validation: dict, allow: bool = True):
        seed = folder / "papers.json"
        seed.write_text(json.dumps([{"id": "core1", "title": "Lithium diffusion in garnet electrolytes", "doi": "10.1000/core"}]), encoding="utf-8")
        with patch.object(library_store, "ROOT", folder), \
                patch.object(library_store, "load_library_papers",
                             side_effect=lambda *a, **k: json.loads(seed.read_text(encoding="utf-8"))), \
                patch.object(library_store, "USER_PAPERS", folder / "user.json"), \
                patch.object(library_store, "MANIFEST", folder / "manifest.json"), \
                patch.object(library_store, "PDF_DIR", folder / "pdfs"), \
                patch("library_store._first_pages_text", return_value=("text", 3, {})), \
                patch("library_store.validate_pdf", return_value=validation), \
                patch("library_store.rebuild_fulltext_index"):
            return library_store.ingest_pdf(b"%PDF-1.7 fake", "x.pdf", {"doi": "10.1000/core", "year": "2020"},
                                            allow_attach_to_existing=allow)

    def test_pdf_must_match_catalogued_paper_identity(self) -> None:
        mismatch = {"valid_pdf": True, "document_kind": "article", "identity_valid": False,
                    "identity_rejection_reason": "document_identity_mismatch"}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError) as raised:
                self._ingest(Path(folder), mismatch)
            self.assertIn("不一致", str(raised.exception))
            self.assertFalse((Path(folder) / "pdfs" / "core1.pdf").exists())

    def test_remote_upload_cannot_attach_to_existing_paper(self) -> None:
        good = {"valid_pdf": True, "document_kind": "article", "identity_valid": True}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self._ingest(Path(folder), good, allow=False)
            result = self._ingest(Path(folder), good, allow=True)
            self.assertFalse(result["created"])
            self.assertTrue((Path(folder) / "pdfs" / "core1.pdf").exists())


class FetchUrlTests(unittest.TestCase):
    def test_only_public_https_urls_are_fetched(self) -> None:
        for url in ("file:///etc/passwd", "ftp://example.org/a.pdf", "http://example.org/a.pdf",
                    "https://127.0.0.1/a.pdf", "https://10.0.0.5/a.pdf", "https://[::1]/a.pdf",
                    "https://user:pw@example.org/a.pdf", "https://169.254.169.254/latest"):
            with self.subTest(url=url):
                self.assertFalse(_is_public_https_url(url))
                with self.assertRaises(OSError):
                    request(url)

    def test_public_https_host_is_allowed(self) -> None:
        fake = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("socket.getaddrinfo", return_value=fake):
            self.assertTrue(_is_public_https_url("https://example.org/a.pdf"))


class PublicationRuleTests(unittest.TestCase):
    def test_new_secret_and_personal_data_shapes_are_detected(self) -> None:
        samples = {
            "credential_format": [
                "-----BEGIN " + "PRIVATE KEY-----",
                "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----",
                "Authorization: Bearer " + "test_" + "Zx9" * 12,
                "AIza" + "S" * 35,
                "hf_" + "a1B2" * 9,
            ],
            "phone_number": ["联系 " + "138" + "12345678", "138" + "-1234-5678"],
            "email_address": ["mailto:" + "someone" + "@example.edu.cn"],
            "windows_user_path": ["/" + "Users/" + "alice/Documents", '"C:\\\\' + 'Users\\\\' + 'bob\\\\x"'],
            "local_drive_path": ["E:\\" + "读论文" + "\\notes.md"],
            "secret_assignment": ["export " + "BATTERY_AGENT_ACCESS_TOKEN=" + "f" * 48],
            "signed_url": ["https://d1.cloudfront.net/a.pdf?" + "Policy=abc&" + "Key-Pair-Id=APKA"],
        }
        for kind, texts in samples.items():
            for text in texts:
                with self.subTest(kind=kind, text=text[:12]):
                    self.assertIn(kind, {item.type for item in scan_text(text, "fixture.md")})

    def test_placeholders_and_ordinary_text_stay_clean(self) -> None:
        for text in ("Bearer test-access-token-123456", "doi 10.1016/j.ensm.2023.102964",
                     "https://doi.org/10.1038/s41586-019-1234-5", "set BATTERY_AGENT_ACCESS_TOKEN=<your-key>",
                     "Contact via https://github.com/user@example"):
            with self.subTest(text=text):
                self.assertEqual(scan_text(text, "fixture.md"), [])

    def test_new_forbidden_paths(self) -> None:
        for path in ("keys/server.pem", "tls.key", "cert.p12", "id_rsa", "home/.ssh/id_ed25519", "export/savedrecs.ciw",
                     "zotero.ris", "cache.db", "draft.docx", ".netrc"):
            with self.subTest(path=path):
                self.assertTrue(FORBIDDEN_PATH.search(path))
        for path in ("docs/index.html", "data/papers.json", "static/key-points.js"):
            with self.subTest(path=path):
                self.assertFalse(FORBIDDEN_PATH.search(path))

    def test_workstation_fields_are_private_in_json(self) -> None:
        for key in ("local_pdf", "original_filename", "data_file", "fulltext_file"):
            with self.subTest(key=key):
                findings = scan_text(json.dumps({key: "x"}), "fixture.json")
                self.assertTrue(any(item.type == "private_evidence_value" for item in findings))


if __name__ == "__main__":
    unittest.main()
