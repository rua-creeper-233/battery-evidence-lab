import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from publication_safety import PublicationSafetyError, assert_clean, scan_revision_snapshot


class RevisionSnapshotSafetyTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        env = os.environ.copy()
        fixture_email = "fixture" + "@" + "example.invalid"
        env.update({"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": fixture_email,
                    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": fixture_email})
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True, env=env)
        return result.stdout.strip()

    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix=".publication-test-", dir=Path.cwd()))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.git(root, "init", "-b", "main")
        (root / "README.md").write_text("safe\n", encoding="utf-8")
        self.git(root, "add", "README.md")
        self.git(root, "commit", "-m", "safe")
        return root

    def test_clean_snapshot_and_annotated_tag_pass(self):
        root = self.make_repo()
        commit = self.git(root, "rev-parse", "HEAD")
        self.assertEqual(scan_revision_snapshot(root, commit), [])
        self.git(root, "tag", "-a", "safe-v1", "-m", "safe release")
        tag_object = self.git(root, "rev-parse", "safe-v1")
        self.assertEqual(scan_revision_snapshot(root, tag_object), [])

    def test_alternate_forbidden_snapshot_is_rejected(self):
        root = self.make_repo()
        self.git(root, "checkout", "-b", "alternate")
        private = root / "private" / "session.json"
        private.parent.mkdir()
        private.write_text("fixture\n", encoding="utf-8")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "alternate private snapshot")
        alternate = self.git(root, "rev-parse", "HEAD")
        self.git(root, "checkout", "main")
        with self.assertRaises(PublicationSafetyError):
            assert_clean(scan_revision_snapshot(root, alternate))

    def test_revision_requires_full_object_id(self):
        with self.assertRaises(PublicationSafetyError):
            scan_revision_snapshot(Path.cwd(), "HEAD")

    def test_hook_checks_every_pushed_ref_and_skips_deletions(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX shell unavailable; hook is also exercised in Linux CI")
        root = self.make_repo()
        project = Path(__file__).resolve().parents[1]
        for name in ("publication_safety.py", "history_safety.py"):
            shutil.copyfile(project / name, root / name)
        hook = root / "pre-push"
        shutil.copyfile(project / ".githooks" / "pre-push", hook)
        clean = self.git(root, "rev-parse", "HEAD")
        self.git(root, "checkout", "-b", "alternate")
        private = root / "private" / "fixture.txt"
        private.parent.mkdir()
        private.write_text("fixture\n", encoding="utf-8")
        self.git(root, "add", "private/fixture.txt")
        self.git(root, "commit", "-m", "forbidden path")
        self.git(root, "tag", "-a", "bad-tag", "-m", "fixture")
        bad_tag = self.git(root, "rev-parse", "bad-tag")
        self.git(root, "checkout", "main")
        zeros = "0" * 40
        clean_line = f"refs/heads/main {clean} refs/heads/main {zeros}\n"
        deletion = f"(delete) {zeros} refs/heads/removed {clean}\n"
        bad_line = f"refs/tags/bad-tag {bad_tag} refs/tags/bad-tag {zeros}\n"
        env = {**os.environ, "PUBLICATION_PYTHON": sys.executable}
        def run(updates):
            return subprocess.run([shell, str(hook)], cwd=root, input=updates,
                                  text=True, capture_output=True, env=env, timeout=40)
        accepted = run(clean_line + deletion)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        rejected = run(clean_line + bad_line)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("forbidden_path", rejected.stdout)


if __name__ == "__main__":
    unittest.main()
