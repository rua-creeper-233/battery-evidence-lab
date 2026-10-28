import json
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import build_static_qa


ROOT = Path(__file__).resolve().parents[1]


class StaticQATest(unittest.TestCase):
  def fixtures(self):
    papers = json.loads((ROOT / "data/papers.json").read_text(encoding="utf-8"))[:2]
    route = json.loads((ROOT / "data/learning_route.json").read_text(encoding="utf-8"))
    titles = json.loads((ROOT / "data/paper_titles_zh.json").read_text(encoding="utf-8"))
    return papers, route, titles

  def test_dynamic_build_is_pure_and_source_bound(self):
    papers, route, titles = self.fixtures()
    with patch.object(build_static_qa, "_read", side_effect=AssertionError("unexpected disk read")):
      result = build_static_qa.build(papers, route, titles)
      self.assertEqual((result["catalog_count"], result["qa_count"]), (2, 8))
      self.assertTrue(build_static_qa.validate(result, papers, route, titles))
    for field, value in (("summary", "changed summary"), ("methods", ["new method"]), ("scope_note", "new scope")):
      stale = copy.deepcopy(papers)
      stale[0][field] = value
      with self.subTest(field=field), self.assertRaises(ValueError):
        build_static_qa.validate(result, stale, route, titles)

  def test_tampered_dataset_is_rejected(self):
    papers, route, titles = self.fixtures()
    result = build_static_qa.build(papers, route, titles)
    def check_mutation(change):
      data = copy.deepcopy(result)
      change(data)
      with self.assertRaises(ValueError):
        build_static_qa.validate(data, papers, route, titles)
    for field, value in (("answer", "invented 400 eV"), ("question", "invented question"),
                         ("source_fields", ["local_pdf"]), ("source_urls", ["http://example.org"])):
      with self.subTest(field=field):
        check_mutation(lambda d: d["entries"][0]["qas"][0].__setitem__(field, value))
    check_mutation(lambda d: d.__setitem__("evidence_level", "fulltext_verified"))
    check_mutation(lambda d: d.__setitem__("as_of", "2026-99-99"))
    check_mutation(lambda d: d["entries"][0].__setitem__("private_key", "not_public"))

  def test_static_dataset_coverage_and_provenance(self):
    data = json.loads((ROOT / "data" / "static_qa.json").read_text(encoding="utf-8"))
    papers = json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8"))
    self.assertTrue(build_static_qa.validate(data, papers))
    self.assertEqual(len(data["entries"]), 256)
    self.assertEqual(sum(len(e["qas"]) for e in data["entries"]), 1024)
    self.assertEqual(len({e["doi"] for e in data["entries"]}), 256)
    self.assertTrue(all(q["source_urls"] == [f"https://doi.org/{e['doi']}"] for e in data["entries"] for q in e["qas"]))
    self.assertEqual(data["as_of"], "2026-10-25")


  def test_answers_use_concise_metadata_boundaries(self):
    data = json.loads((ROOT / "data" / "static_qa.json").read_text(encoding="utf-8"))
    qas = [q for e in data["entries"] for q in e["qas"]]
    answers = [q["answer"] for q in qas]
    filler = ("完整复现实验协议", "具体版本、参数和步骤需核对原文", "摘要/正文参数仍需按来源逐项复核", "面向电池电解液、固态电解质、正极/界面模拟的可复用计算文献")
    self.assertTrue(all(not any(token in answer for token in filler) for answer in answers))
    self.assertTrue(all(q["answer"].startswith("目录列出的方法/工具标签：") for q in qas if q["intent"] == "methods"))
    self.assertTrue(all(q["answer"].startswith("范围提示：") for q in qas if q["intent"] == "limitations"))
    self.assertTrue(any("已登记书目，尚无内容摘录。" in answer for answer in answers))
    self.assertTrue(any("范围提示：" in answer and answer != "范围提示：未提供范围说明。" for answer in answers))

if __name__ == "__main__":
    unittest.main()
