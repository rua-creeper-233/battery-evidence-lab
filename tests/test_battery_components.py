import copy
import json
from pathlib import Path
import unittest

from validate_battery_components import ComponentValidationError, validate


ROOT = Path(__file__).resolve().parents[1]


class BatteryComponentTests(unittest.TestCase):
    def setUp(self):
        self.papers = json.loads((ROOT / "data/papers.json").read_text(encoding="utf-8"))
        self.data = json.loads((ROOT / "data/battery_components.json").read_text(encoding="utf-8"))

    def test_real_map_and_empty_category(self):
        self.assertIs(validate(self.data, self.papers), self.data)
        data = copy.deepcopy(self.data)
        data["components"][0]["papers"] = []
        validate(data, self.papers)

    def test_rejects_stale_citation_private_fields_and_unknown_components(self):
        for mutation in (
            lambda d: d.update({"private_map": {}}),
            lambda d: d["components"][0].update({"attachment_key": "never-public"}),
            lambda d: d["components"][0]["papers"][0].update({"doi": "10.1000/not-the-paper"}),
            lambda d: d["components"][0].update({"id": "unknown"}),
            lambda d: d["components"].__setitem__(1, copy.deepcopy(d["components"][0])),
        ):
            data = copy.deepcopy(self.data)
            mutation(data)
            with self.assertRaises(ComponentValidationError):
                validate(data, self.papers)

    def test_rejects_unsafe_or_unapproved_source_and_duplicate_paper(self):
        for url in ("javascript:alert(1)", "https://energy.gov.evil.test/paper",
                    "https://user:secret@energy.gov/paper", "https://energy.gov/paper?example=1"):
            data = copy.deepcopy(self.data)
            data["sources"][0]["url"] = url
            with self.assertRaises(ComponentValidationError):
                validate(data, self.papers)
        data = copy.deepcopy(self.data)
        data["components"][0]["papers"].append(copy.deepcopy(data["components"][0]["papers"][0]))
        with self.assertRaises(ComponentValidationError):
            validate(data, self.papers)


if __name__ == "__main__":
    unittest.main()
