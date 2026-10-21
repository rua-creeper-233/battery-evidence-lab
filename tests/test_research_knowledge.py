import copy
import unittest

from validate_research_knowledge import KnowledgeValidationError, validate


PAPERS = [{"id": "p1", "doi": "10.1000/ABC"}, {"id": "p2", "doi": "10.1000/DEF"}]


def card(cid="c1"):
    return {"id": cid, "kind": "foundation", "question": "什么是 DFT？", "aliases": ["DFT是什么", "密度泛函理论"], "all_of": [["DFT", "密度泛函"], ["基础"]], "answer": "答案", "steps": ["读定义"], "checks": ["核对体系"], "boundary": "需要验证", "sources": [{"paper_id": "p1", "doi": "10.1000/ABC", "locator": "摘要", "note": "基础定义"}], "documentation": [{"label": "VASP", "url": "https://www.vasp.at/wiki/DFT", "locator": "DFT"}], "tags": ["基础"]}


class ResearchKnowledgeValidationTests(unittest.TestCase):
    def test_valid_and_exact_citation(self):
        data = {"schema_version": 1, "as_of": "2026-10-20", "cards": [card()]}
        self.assertIs(validate(data, PAPERS), data)
        bad = copy.deepcopy(data); bad["cards"][0]["sources"][0]["doi"] = "10.1000/abc"
        with self.assertRaises(KnowledgeValidationError): validate(bad, PAPERS)

    def test_rejects_private_unknown_duplicate_and_unsafe(self):
        base = {"schema_version": 1, "as_of": "2026-10-20", "cards": [card()]}
        for mutate in (lambda d: d.update({"private": 1}), lambda d: d["cards"].append(copy.deepcopy(d["cards"][0])), lambda d: d["cards"][0].update({"x": 1}), lambda d: d["cards"][0]["documentation"][0].update({"url": "http://evil.test"})):
            bad = copy.deepcopy(base); mutate(bad)
            with self.assertRaises(KnowledgeValidationError): validate(bad, PAPERS)

    def test_content_limits_and_missing_sources(self):
        base = {"schema_version": 1, "as_of": "2026-10-20", "cards": [card()]}
        for field in ("steps", "checks"):
            bad = copy.deepcopy(base); bad["cards"][0][field] = []
            with self.assertRaises(KnowledgeValidationError): validate(bad, PAPERS)
        bad = copy.deepcopy(base); bad["cards"][0]["sources"] = []
        with self.assertRaises(KnowledgeValidationError): validate(bad, PAPERS)


if __name__ == "__main__": unittest.main()
