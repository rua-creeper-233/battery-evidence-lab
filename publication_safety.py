"""Fail-closed checks for the public GitHub Pages publication bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import os
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class PublicationSafetyError(ValueError):
    """Raised when a public artifact cannot be proven safe to publish."""


PUBLIC_ZOTERO_KEYS = {"visibility", "items"}
FORBIDDEN_PATH = re.compile(
    r"(?:^|/)(?:private|distill|\.codex|\.agents|private_backups|backups|literature/(?:pdfs|text)|models?|outputs?|training/(?:checkpoints|output))(?:/|$)|"
    r"(?:^|/)(?:local[_-](?:auth|authentication|logs?)|(?:\.?)auth|(?:\.?)logs?)(?:/|$)|"
    r"(?:^|/)\.env(?:[./]|$)|(?:^|/)(?:fulltext_chunks\.jsonl|old_manifest\.json|zotero-links\.local\.json|SECURITY_PRIVACY_AUDIT_[^/]+\.md)$|"
    r"(?:^|/)literature/manifest\.json$|(?:\.(?:pdf|safetensors|gguf|bin|pt|pth|zip|7z|sqlite)(?:-shm|-wal)?$)", re.I
)
_INSTITUTION_TRACE_SUBJECTS = ("华南" + "师范大学", "华" + "师", "西安" + "交通大学", "西" + "交")
_INSTITUTION_TRACE_EVENTS = (("机构" + "会话"), ("校内" + "授权"), ("授权" + "下载"))
_INSTITUTION_TRACE_PATTERN = rf"(?:{'|'.join(map(re.escape, _INSTITUTION_TRACE_SUBJECTS))}).{{0,20}}(?:{'|'.join(map(re.escape, _INSTITUTION_TRACE_EVENTS))})"
CONTENT_RULES = (
    ("credential_format", re.compile(r"(?:AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----|Bearer\s+(?!test[-_]|example[-_]|placeholder[-_])[A-Za-z0-9._-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,})", re.I)),
    ("signed_url", re.compile(r"https?://[^\s\"']+(?:[?&](?:sig|signature|x-amz-signature|token|expires|x-goog-signature)=|drive\.usercontent\.google\.com/download\?id=)[^\s\"']*", re.I)),
    ("zotero_private_key", re.compile(r"zotero://(?:items/|(?:open-pdf|select)/(?:library|groups/\d+)/items/)[A-Z0-9]{8}(?=[/?#\s\"']|$)", re.I)),
    ("windows_user_path", re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/](?![<\[(])[^\\/\s<>'\"]+|/mnt/[a-z]/Users/(?![<\[(])[^/\s<>'\"]+|/home/(?![<\[(])[^/\s<>'\"]+)", re.I)),
    ("email_address", re.compile(r"(?<![A-Za-z0-9._%+:/-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])")),
    ("phone_number", re.compile(r"(?:\+\d[\d ()-]{8,}\d|\b\d{3}[- )]\d{3}[- ]\d{4}\b)")),
    ("fulltext_verification", re.compile(r"verified_local_pdf[_-]\d{4}-\d{2}-\d{2}", re.I)),
    ("personal_access_trace", re.compile(
        r"(?:verified_institution_session[_-]\d{4}-\d{2}-\d{2}|"
        r"(?:institution_access_trace|specific[_-]?user[_-]?session|"
        r"authorized[_-]?(?:download|access)|download[_-]?authori[sz]ation|"
        r"user[_-]?session[_-]?id)\s*(?:[:=]|=>)\s*"
        r"(?:20\d{2}[-_]\d{2}[-_]\d{2}|[A-Z0-9][A-Z0-9_-]{7,})|"
        rf"(?:{_INSTITUTION_TRACE_PATTERN}))", re.I)),
    ("download_authorization", re.compile(
        r"(?:oauth[_-]?download[_-]?(?:code|token)|download[_-]?authorization[_-]?code|"
        r"authorization[_-]?code)\s*(?:[:=]|=>)\s*[A-Z0-9][A-Z0-9._-]{7,}", re.I)),
)
PRIVATE_DATA_FIELDS = {
    "local_pdf_url", "fulltext_paper_ids", "fulltext_paper_count",
    "private_pdf", "restricted_pdf", "model_weights", "attachment_key", "item_key",
    "local_fulltext_papers", "local_fulltext_missing", "indexed_chunks", "indexed_papers",
    "api_key", "apikey", "access_token", "bearer_token", "password", "client_secret", "private_key",
    "access_basis", "institution_access_trace", "download_authorization", "authorization_code",
    "oauth_download_code", "user_session_id", "specific_user_session",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    type: str


_PUBLIC_PNG_PATHS = {"static/share-card.png", "docs/share-card.png"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_MAX_BYTES = 8 * 1024 * 1024
_PNG_MAX_CHUNK_BYTES = 4 * 1024 * 1024
_PNG_IMAGE_CHUNKS = {"IHDR", "PLTE", "IDAT", "IEND", "tRNS", "cHRM", "gAMA", "sRGB", "pHYs", "bKGD"}
_FULL_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
_PUBLIC_PNG_SHA256 = "bbea9686cb32a2f6a5736900aee8f7a5e90ed0cfef6a892e47ca7da7bb256324"


def _validate_public_png(data: bytes, path: str) -> None:
    """Validate the one generated PNG shape permitted in publication inputs."""
    if (len(data) > _PNG_MAX_BYTES or not data.startswith(_PNG_SIGNATURE)
            or hashlib.sha256(data).hexdigest() != _PUBLIC_PNG_SHA256):
        raise PublicationSafetyError(f"invalid publication PNG: {path}")
    offset = len(_PNG_SIGNATURE)
    chunks: list[str] = []
    while offset < len(data):
        if len(data) - offset < 12:
            raise PublicationSafetyError(f"truncated publication PNG: {path}")
        length = struct.unpack_from(">I", data, offset)[0]
        if length > _PNG_MAX_CHUNK_BYTES:
            raise PublicationSafetyError(f"oversized publication PNG chunk: {path}")
        end = offset + 12 + length
        if end > len(data):
            raise PublicationSafetyError(f"truncated publication PNG chunk: {path}")
        raw_type = data[offset + 4:offset + 8]
        try:
            chunk_type = raw_type.decode("ascii")
        except UnicodeDecodeError as exc:
            raise PublicationSafetyError(f"invalid publication PNG chunk: {path}") from exc
        if not re.fullmatch(r"[A-Za-z]{4}", chunk_type) or chunk_type not in _PNG_IMAGE_CHUNKS:
            raise PublicationSafetyError(f"disallowed publication PNG chunk: {path}")
        payload_start = offset + 8
        payload_end = payload_start + length
        expected_crc = struct.unpack_from(">I", data, payload_end)[0]
        actual_crc = zlib.crc32(data[offset + 4:payload_end]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise PublicationSafetyError(f"invalid publication PNG CRC: {path}")
        chunks.append(chunk_type)
        if chunk_type == "IHDR":
            if length != 13 or struct.unpack_from(">II", data, payload_start) != (1200, 630):
                raise PublicationSafetyError(f"publication PNG must be 1200x630: {path}")
        elif chunk_type == "IEND" and length != 0:
            raise PublicationSafetyError(f"invalid publication PNG IEND: {path}")
        offset = end
        if chunk_type == "IEND":
            if offset != len(data):
                raise PublicationSafetyError(f"trailing publication PNG data: {path}")
            break
    if chunks[:1] != ["IHDR"] or chunks[-1:] != ["IEND"] or "IDAT" not in chunks:
        raise PublicationSafetyError(f"incomplete publication PNG: {path}")


def _scan_blob(name: str, data: bytes) -> list[Finding]:
    name = name.replace("\\", "/")
    if FORBIDDEN_PATH.search(name):
        return [Finding(name, 0, "forbidden_path")]
    if name in _PUBLIC_PNG_PATHS:
        _validate_public_png(data, name)
        return []
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicationSafetyError(f"unable to decode publication input: {name}") from exc
    return scan_text(content, name, include_structured_fields=name.lower().endswith((".json", ".jsonl")))


def validate_public_zotero_map(value: object) -> dict:
    """Require the intentionally empty public Zotero allowlist."""
    if isinstance(value, (str, Path)):
        import json
        value = json.loads(Path(value).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != PUBLIC_ZOTERO_KEYS:
        raise PublicationSafetyError("public Zotero map must contain exactly visibility and items")
    if value.get("visibility") != "public_sanitized":
        raise PublicationSafetyError("public Zotero map must be public_sanitized")
    if not isinstance(value.get("items"), dict) or value["items"]:
        raise PublicationSafetyError("public Zotero items must be an empty object")
    return value


# Descriptive aliases kept small so callers do not need to depend on the
# implementation name used by the build script.
validate_public_zotero = validate_public_zotero_map


def sanitize_method_evidence(value: dict) -> dict:
    """Return only metadata and short method signals; omit local evidence locators."""
    if not isinstance(value, dict) or not isinstance(value.get("papers"), dict):
        raise PublicationSafetyError("method evidence must contain a papers object")
    # Method extraction is local evidence, not a publication entitlement.  A
    # non-empty map would disclose which papers have private holdings, so the
    # public payload is intentionally empty until a separately reviewed map is
    # designed.
    papers = {}
    return {"schema_version": 1, "review_status": value.get("review_status", ""),
            "notice_zh": value.get("notice_zh", ""), "papers": papers}


def scan_text(text: str, path: str = "<memory>", *, include_structured_fields: bool | None = None) -> list[Finding]:
    if include_structured_fields is None:
        include_structured_fields = path.lower().endswith((".json", ".jsonl"))
    findings = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for kind, rule in CONTENT_RULES:
            if rule.search(line):
                findings.append(Finding(path, line_no, kind))
    if include_structured_fields:
        try:
            values = [json.loads(line) for line in text.splitlines() if line.strip()] if path.lower().endswith(".jsonl") else [json.loads(text)]
        except json.JSONDecodeError as exc:
            raise PublicationSafetyError(f"invalid structured publication input: {path}") from exc

        def walk(value, parent_key=""):
            if isinstance(value, dict):
                for key, item in value.items():
                    key_name = str(key).lower()
                    sensitive_fulltext = key_name == "fulltext" and parent_key == "verification"
                    if (key_name in PRIVATE_DATA_FIELDS or sensitive_fulltext) and item not in (None, "", {}, []):
                        key_match = re.search(r'"' + re.escape(str(key)) + r'"\s*:', text)
                        line = text.count("\n", 0, key_match.start()) + 1 if key_match else 1
                        findings.append(Finding(path, line, "private_evidence_value"))
                    walk(item, key_name)
            elif isinstance(value, list):
                for item in value:
                    walk(item, parent_key)

        for value in values:
            walk(value)
        if path.replace("\\", "/").endswith("zotero-links.json"):
            validate_public_zotero_map(values[0])
    return findings


def scan_files(paths: Iterable[Path], root: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    root = root or Path.cwd()
    for path in paths:
        rel = path.relative_to(root).as_posix() if path.is_absolute() and path.is_relative_to(root) else str(path).replace("\\", "/")
        if FORBIDDEN_PATH.search(rel):
            findings.append(Finding(rel, 0, "forbidden_path"))
            continue
        if path.is_file():
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise PublicationSafetyError(f"unable to read publication input: {rel}") from exc
            findings.extend(_scan_blob(rel, data))
    return findings


scan_public_bundle = scan_files


def _git_executable() -> str:
    configured = os.environ.get("PUBLICATION_GIT_EXE", "")
    if configured:
        candidate = Path(configured)
        if not candidate.is_file() or candidate.name.lower() not in {"git", "git.exe"}:
            raise PublicationSafetyError("PUBLICATION_GIT_EXE is not a safe git executable")
        return str(candidate)
    found = shutil.which("git")
    if not found:
        raise PublicationSafetyError("git executable is unavailable")
    return found


def scan_staged_snapshot(root: Path) -> list[Finding]:
    """Scan exactly the complete index snapshot, without printing values."""
    git = _git_executable()
    safe_root = str(root.resolve())
    result = subprocess.run([git, "-c", f"safe.directory={safe_root}", "ls-files", "-s", "-z"], cwd=root, text=False, capture_output=True, check=False)
    if result.returncode:
        raise PublicationSafetyError("unable to enumerate the staged publication snapshot")
    findings: list[Finding] = []
    for record in result.stdout.decode("utf-8").split("\0"):
        if not record:
            continue
        try:
            _, name = record.split("\t", 1)
        except ValueError as exc:
            raise PublicationSafetyError("invalid git index record") from exc
        blob = subprocess.run([git, "-c", f"safe.directory={safe_root}", "show", f":{name}"], cwd=root, text=False, capture_output=True, check=False)
        if blob.returncode:
            raise PublicationSafetyError("unable to read a staged publication file")
        findings.extend(_scan_blob(name, blob.stdout))
    return findings


def scan_revision_snapshot(root: Path, revision: str) -> list[Finding]:
    """Scan a full commit tree without touching the checkout or index."""
    if not _FULL_OBJECT_ID.fullmatch(revision):
        raise PublicationSafetyError("revision must be a full 40- or 64-character object id")
    git = _git_executable()
    safe_root = str(root.resolve())
    resolved = subprocess.run(
        [git, "-c", f"safe.directory={safe_root}", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        cwd=root, text=False, capture_output=True, check=False,
    )
    resolved_revision = resolved.stdout.strip().decode("ascii", errors="ignore")
    if resolved.returncode or not _FULL_OBJECT_ID.fullmatch(resolved_revision):
        raise PublicationSafetyError("unable to resolve revision")
    tree = subprocess.run(
        [git, "-c", f"safe.directory={safe_root}", "ls-tree", "-r", "-z", "--name-only", resolved_revision],
        cwd=root, text=False, capture_output=True, check=False,
    )
    if tree.returncode:
        raise PublicationSafetyError("unable to enumerate revision snapshot")
    findings: list[Finding] = []
    for raw_name in tree.stdout.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8")
        blob = subprocess.run(
            [git, "-c", f"safe.directory={safe_root}", "show", f"{resolved_revision}:{name}"],
            cwd=root, text=False, capture_output=True, check=False,
        )
        if blob.returncode:
            raise PublicationSafetyError("unable to read revision snapshot file")
        findings.extend(_scan_blob(name, blob.stdout))
    return findings


def assert_clean(findings: Iterable[Finding]) -> None:
    findings = list(findings)
    if findings:
        summary = ", ".join(f"{f.path}:{f.line}:{f.type}" for f in findings[:20])
        raise PublicationSafetyError(f"publication safety check failed ({summary})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan staged or public publication inputs without printing sensitive values")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.required = True
    modes.add_argument("--staged", action="store_true", help="scan the complete Git index snapshot")
    modes.add_argument("--public-bundle", action="store_true", help="scan tracked files under docs/")
    modes.add_argument("--revision", help="scan a full 40- or 64-character commit object id")
    args = parser.parse_args()
    try:
        if args.staged:
            findings = scan_staged_snapshot(args.root)
        elif args.public_bundle:
            findings = scan_files((args.root / "docs").rglob("*"), args.root)
        else:
            findings = scan_revision_snapshot(args.root, args.revision)
    except PublicationSafetyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    payload = {"ok": not findings, "findings": [{"path": f.path, "line": f.line, "type": f.type} for f in findings]}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
