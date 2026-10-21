import tempfile
import unittest
from pathlib import Path

from build_pages import write_utf8


class BuildPortabilityTests(unittest.TestCase):
    def test_generated_text_uses_utf8_and_lf_on_every_platform(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "page.html"
            content = "论文\n第二行\n"
            write_utf8(target, content)
            self.assertEqual(target.read_bytes(), content.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
