"""Read-only Git history path safety checks.

It inventories every path reachable from a ref.  With ``--scan-content``
(used by the pre-push hook and CI) it also runs the publication content rules
on every distinct reachable blob, so a secret committed under an innocent file
name is still found.  It never prints file contents, inspects unreachable
objects, or rewrites history.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from tools.publication_safety import FORBIDDEN_PATH, PublicationSafetyError, _git_executable, _scan_blob


class HistorySafetyError(ValueError):
    """Raised when a history inventory cannot be collected safely."""


_CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")
_OBJECT_ID = re.compile(rb"^[0-9a-fA-F]{40,64}$")
# Historical blobs reviewed by hand and known to hold only test fixtures, keyed
# by exact object id so any edit to the content is scanned again.
#   b711f9d...: tests/test_dataset_splits.py with a fake "access_token=secret"
#   URL used to test public_resources(); split in later revisions.
REVIEWED_FIXTURE_BLOBS = frozenset({
    "b711f9dc5bcd329b0f03bf24006ca2bb9a23bd8e",
})


def _validate_ref(ref: str) -> str:
    """Reject ref values that could be malformed or used as options."""
    if not isinstance(ref, str) or not ref or ref.startswith(("-", "^")):
        raise HistorySafetyError("invalid git ref")
    if "\x00" in ref or _CONTROL_OR_SPACE.search(ref):
        raise HistorySafetyError("invalid git ref")
    # These are rejected by Git's ref parser and are called out here so the
    # scanner fails before any inventory command is attempted.
    if any(part in {"", ".", ".."} for part in ref.split("/")) or ref.endswith(".") or ".." in ref:
        raise HistorySafetyError("invalid git ref")
    if any(token in ref for token in ("@{", "\\")):
        raise HistorySafetyError("invalid git ref")
    return ref


def _resolve_commit(root: Path, ref: str) -> str:
    """Resolve a user ref to exactly one commit object before inventorying it."""
    ref = _validate_ref(ref)
    git = _git_executable()
    safe_root = root.resolve().as_posix()
    command = [
        git,
        "-c",
        f"safe.directory={safe_root}",
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{ref}^{{commit}}",
    ]
    try:
        result = subprocess.run(command, cwd=root, text=False, capture_output=True, check=False)
    except (OSError, ValueError) as exc:
        raise HistorySafetyError("unable to resolve git ref") from exc
    if result.returncode:
        raise HistorySafetyError("unable to resolve git ref")
    lines = result.stdout.splitlines()
    if len(lines) != 1 or not _OBJECT_ID.fullmatch(lines[0]):
        raise HistorySafetyError("invalid resolved git ref")
    return lines[0].decode("ascii")


def _safe_path(raw: bytes) -> str:
    """Decode a Git path for JSON without exposing undecodable bytes."""
    value = raw.decode("utf-8", errors="replace").replace("\\", "/")
    # json.dumps escapes control characters; retaining them here keeps the
    # inventory deterministic while ensuring they are never printed raw.
    return value


def _reachable_forbidden_paths(root: Path, ref: str) -> set[str]:
    """Return forbidden paths reachable from *ref*, without blob reads."""
    commit = _resolve_commit(root, ref)
    git = _git_executable()
    safe_root = root.resolve().as_posix()
    command = [git, "-c", f"safe.directory={safe_root}", "rev-list", "--format=%T", "--no-commit-header", commit]
    try:
        result = subprocess.run(command, cwd=root, text=False, capture_output=True, check=False)
    except (OSError, ValueError) as exc:
        raise HistorySafetyError("unable to enumerate reachable git history") from exc
    if result.returncode:
        raise HistorySafetyError("unable to enumerate reachable git history")

    paths: set[str] = set()
    tree_ids = result.stdout.splitlines()
    if not tree_ids or any(not _OBJECT_ID.fullmatch(tree_id) for tree_id in tree_ids):
        raise HistorySafetyError("invalid git tree inventory")
    for tree_id in dict.fromkeys(tree_ids):
        tree = tree_id.decode("ascii")
        tree_command = [
            git,
            "-c",
            f"safe.directory={safe_root}",
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            tree,
        ]
        try:
            tree_result = subprocess.run(tree_command, cwd=root, text=False, capture_output=True, check=False)
        except (OSError, ValueError) as exc:
            raise HistorySafetyError("unable to enumerate reachable git trees") from exc
        if tree_result.returncode:
            raise HistorySafetyError("unable to enumerate reachable git trees")
        for raw_path in tree_result.stdout.split(b"\0"):
            if not raw_path:
                continue
            path = _safe_path(raw_path)
            if FORBIDDEN_PATH.search(path):
                paths.add(path)
    return paths


def _reachable_content_findings(root: Path, ref: str) -> set[tuple[str, str]]:
    """Scan each distinct blob reachable from *ref* with the content rules.

    Returns (path, finding type) pairs only; values are never collected.
    """
    commit = _resolve_commit(root, ref)
    git = _git_executable()
    safe_root = root.resolve().as_posix()
    tree_list = subprocess.run(
        [git, "-c", f"safe.directory={safe_root}", "rev-list", "--format=%T", "--no-commit-header", commit],
        cwd=root, text=False, capture_output=True, check=False,
    )
    if tree_list.returncode:
        raise HistorySafetyError("unable to enumerate reachable git history")
    blob_paths: dict[str, str] = {}
    for tree_id in dict.fromkeys(tree_list.stdout.splitlines()):
        if not _OBJECT_ID.fullmatch(tree_id):
            raise HistorySafetyError("invalid git tree inventory")
        entries = subprocess.run(
            [git, "-c", f"safe.directory={safe_root}", "ls-tree", "-r", "-z", tree_id.decode("ascii")],
            cwd=root, text=False, capture_output=True, check=False,
        )
        if entries.returncode:
            raise HistorySafetyError("unable to enumerate reachable git trees")
        for record in entries.stdout.split(b"\0"):
            if not record:
                continue
            meta, _, raw_path = record.partition(b"\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == b"blob" and _OBJECT_ID.fullmatch(parts[2]):
                blob_paths.setdefault(parts[2].decode("ascii"), _safe_path(raw_path))
    findings: set[tuple[str, str]] = set()
    for blob_id, path in blob_paths.items():
        if FORBIDDEN_PATH.search(path) or blob_id in REVIEWED_FIXTURE_BLOBS:
            continue  # reported by the path inventory, or reviewed fixture
        blob = subprocess.run(
            [git, "-c", f"safe.directory={safe_root}", "cat-file", "blob", blob_id],
            cwd=root, text=False, capture_output=True, check=False,
        )
        if blob.returncode:
            raise HistorySafetyError("unable to read a reachable blob")
        try:
            results = _scan_blob(path, blob.stdout)
        except PublicationSafetyError:
            # Undecodable or malformed historical content cannot be proven clean.
            findings.add((path, "unscannable_content"))
            continue
        findings.update((item.path, item.type) for item in results)
    return findings


def _path_records(paths: Iterable[str]) -> list[dict[str, str]]:
    return [{"path": path, "type": "forbidden_path"} for path in sorted(set(paths))]


def audit_history(
    root: Path,
    *,
    baseline: str | None = "origin/main",
    candidate: str = "HEAD",
    full_inventory: bool = False,
    scan_content: bool = False,
) -> dict:
    """Audit candidate reachable paths against an optional acknowledged baseline."""
    root = Path(root)
    candidate_paths = _reachable_forbidden_paths(root, candidate)
    content_findings: set[tuple[str, str]] = set()
    if scan_content:
        content_findings = _reachable_content_findings(root, candidate)
        if baseline is not None:
            content_findings -= _reachable_content_findings(root, baseline)
    baseline_paths: set[str] = set()
    if baseline is not None:
        baseline_paths = _reachable_forbidden_paths(root, baseline)
    newly_introduced = candidate_paths - baseline_paths
    # history_clean describes the candidate history itself, including known
    # legacy findings.  ``ok`` describes whether a new regression was found.
    return {
        "ok": not newly_introduced and not content_findings,
        "history_clean": not candidate_paths and not content_findings,
        "content_findings": [{"path": path, "type": kind} for path, kind in sorted(content_findings)],
        "baseline": {
            "forbidden_paths": _path_records(baseline_paths),
            "count": len(baseline_paths),
        },
        "candidate": {
            "forbidden_paths": _path_records(candidate_paths),
            "count": len(candidate_paths),
        },
        "newly_introduced_forbidden_paths": _path_records(newly_introduced),
        "scope": {
            "reachable_objects_only": True,
            "path_level_only": not scan_content,
            "blob_content_scanned": scan_content,
            "unreachable_objects_scanned": False,
            # Every audit now walks every reachable historical commit tree so
            # identical blobs under different paths cannot hide a finding.
            "full_inventory": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit reachable Git history paths without reading blob contents")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", default="origin/main", help="safe baseline Git ref (default: origin/main)")
    parser.add_argument("--no-baseline", action="store_true", help="perform a full audit without an acknowledged baseline")
    parser.add_argument("--candidate", default="HEAD", help="candidate Git ref (default: HEAD)")
    parser.add_argument(
        "--full-inventory",
        "--fullinventory",
        action="store_true",
        help="label the report as a complete reachable-history inventory",
    )
    parser.add_argument("--scan-content", action="store_true",
                        help="also run publication content rules on every reachable historical blob")
    args = parser.parse_args(argv)
    if args.no_baseline and args.baseline != "origin/main":
        parser.error("--no-baseline cannot be combined with an explicit --baseline")
    baseline = None if args.no_baseline else args.baseline
    try:
        payload = audit_history(
            args.root,
            baseline=baseline,
            candidate=args.candidate,
            full_inventory=args.full_inventory,
            scan_content=args.scan_content,
        )
    except (HistorySafetyError, PublicationSafetyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    if baseline is None and payload["candidate"]["forbidden_paths"]:
        payload["ok"] = False
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
