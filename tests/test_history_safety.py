import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import history_safety


GIT = os.environ.get("PUBLICATION_GIT_EXE", "git")


def git(root: Path, *args: str) -> str:
    result = subprocess.run([GIT, *args], cwd=root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


class HistorySafetyTests(unittest.TestCase):
    def make_repo(self) -> Path:
        folder = Path(tempfile.mkdtemp())
        git(folder, "init", "-b", "main")
        git(folder, "config", "user.email", "fixture" + chr(64) + "example.invalid")
        git(folder, "config", "user.name", "Fixture")
        (folder / "README.md").write_text("safe\n", encoding="utf-8")
        git(folder, "add", "README.md")
        git(folder, "commit", "-m", "initial")
        return folder

    def test_deleted_private_history_is_known_baseline_not_new_regression(self):
        root = self.make_repo()
        private = root / "literature" / "manifest.json"
        private.parent.mkdir()
        private.write_text("private\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "private history")
        old = git(root, "rev-parse", "HEAD")
        private.unlink()
        git(root, "add", "-u")
        git(root, "commit", "-m", "remove private file")
        current = git(root, "rev-parse", "HEAD")
        report = history_safety.audit_history(root, baseline=old, candidate=current)
        self.assertFalse(report["history_clean"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["newly_introduced_forbidden_paths"], [])
        self.assertEqual(report["candidate"]["forbidden_paths"][0]["path"], "literature/manifest.json")

    def test_new_forbidden_path_is_regression(self):
        root = self.make_repo()
        baseline = git(root, "rev-parse", "HEAD")
        private = root / "literature" / "manifest.json"
        private.parent.mkdir()
        private.write_text("private\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "introduce private history")
        report = history_safety.audit_history(root, baseline=baseline, candidate="HEAD")
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["newly_introduced_forbidden_paths"]), 1)

    def test_same_blob_at_allowed_and_forbidden_paths_is_reported(self):
        root = self.make_repo()
        private = root / "literature" / "manifest.json"
        private.parent.mkdir()
        private.write_text("safe\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "path alias")
        report = history_safety.audit_history(root, baseline=None, candidate="HEAD")
        self.assertEqual(
            {entry["path"] for entry in report["candidate"]["forbidden_paths"]},
            {"literature/manifest.json"},
        )

    def test_training_manifest_is_forbidden(self):
        root = self.make_repo()
        path = root / "training" / "manifest.json"
        path.parent.mkdir()
        path.write_text("{}\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "training manifest")
        report = history_safety.audit_history(root, baseline=None, candidate="HEAD")
        self.assertFalse(report["history_clean"])
        self.assertEqual(report["candidate"]["forbidden_paths"][0]["path"], "training/manifest.json")

    def test_staged_uncommitted_path_does_not_affect_head_inventory(self):
        root = self.make_repo()
        private = root / "literature" / "manifest.json"
        private.parent.mkdir()
        private.write_text("staged only\n", encoding="utf-8")
        git(root, "add", ".")
        report = history_safety.audit_history(root, baseline=None, candidate="HEAD")
        self.assertTrue(report["history_clean"])

    def test_invalid_ref_is_rejected_without_git_command(self):
        root = self.make_repo()
        with patch.object(history_safety, "_git_executable", side_effect=AssertionError("must not run git")):
            with self.assertRaises(history_safety.HistorySafetyError):
                history_safety.audit_history(root, baseline=None, candidate="--bad\x00ref")

    def test_failed_git_command_is_sanitized(self):
        root = self.make_repo()
        with patch.object(history_safety, "_git_executable", return_value="does-not-exist"):
            with self.assertRaises(history_safety.HistorySafetyError) as raised:
                history_safety.audit_history(root, baseline=None, candidate="HEAD")
        self.assertEqual(str(raised.exception), "unable to resolve git ref")

    def test_exclusion_refs_are_rejected(self):
        root = self.make_repo()
        for ref in ("^HEAD", "HEAD..HEAD"):
            with self.subTest(ref=ref), self.assertRaises(history_safety.HistorySafetyError):
                history_safety.audit_history(root, baseline=None, candidate=ref)

    def test_non_commit_object_is_rejected(self):
        root = self.make_repo()
        tree = git(root, "rev-parse", "HEAD^{tree}")
        with self.assertRaises(history_safety.HistorySafetyError):
            history_safety.audit_history(root, baseline=None, candidate=tree)

    def test_cli_outputs_json_without_object_ids(self):
        root = self.make_repo()
        result = subprocess.run(
            [os.fspath(Path(os.sys.executable)), "history_safety.py", "--root", os.fspath(root), "--no-baseline"],
            cwd=Path(__file__).parents[1], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["scope"]["path_level_only"])
        self.assertNotRegex(result.stdout, r"\b[0-9a-f]{40,64}\b")


if __name__ == "__main__":
    unittest.main()
