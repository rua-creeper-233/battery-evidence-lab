import subprocess
import sys
import unittest
from pathlib import Path

from maintenance import audit_library, repair_zotero_metadata


class MaintenanceLayoutTests(unittest.TestCase):
    def test_modules_resolve_repository_root_and_private_reports(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit_library.ROOT, root)
        self.assertEqual(audit_library.REPORT_PATH, root / "private" / "FULLTEXT_AUDIT.md")
        self.assertEqual(repair_zotero_metadata.ROOT, root)
        self.assertEqual(repair_zotero_metadata.REPORT, root / "private" / "ZOTERO_METADATA_REPAIR.md")

    def test_read_only_cli_help_uses_maintenance_module(self):
        result = subprocess.run(
            [sys.executable, "-m", "maintenance.import_wos", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Import a WoS plain-text export", result.stdout)


if __name__ == "__main__":
    unittest.main()
