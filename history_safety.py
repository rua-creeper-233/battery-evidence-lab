"""Read-only Git history path safety checks.

This module intentionally inventories reachable object paths only.  It does not
read blob contents, inspect unreachable objects, or rewrite repository history.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from publication_safety import FORBIDDEN_PATH, PublicationSafetyError, _git_executable


class HistorySafetyError(ValueError):
    """Raised when a history inventory cannot be collected safely."""


_CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")
_OBJECT_ID = re.compile(rb"^[0-9a-fA-F]{40,64}$")


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
    safe_root = str(root.resolve())
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
    safe_root = str(root.resolve())
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


def _path_records(paths: Iterable[str]) -> list[dict[str, str]]:
    return [{"path": path, "type": "forbidden_path"} for path in sorted(set(paths))]


def audit_history(
    root: Path,
    *,
    baseline: str | None = "origin/main",
    candidate: str = "HEAD",
    full_inventory: bool = False,
) -> dict:
    """Audit candidate reachable paths against an optional acknowledged baseline."""
    root = Path(root)
    candidate_paths = _reachable_forbidden_paths(root, candidate)
    baseline_paths: set[str] = set()
    if baseline is not None:
        baseline_paths = _reachable_forbidden_paths(root, baseline)
    newly_introduced = candidate_paths - baseline_paths
    # history_clean describes the candidate history itself, including known
    # legacy findings.  ``ok`` describes whether a new regression was found.
    return {
        "ok": not newly_introduced,
        "history_clean": not candidate_paths,
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
            "path_level_only": True,
            "blob_content_scanned": False,
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
