import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import build_domestic_papers as builder


def fixture():
    papers = [{"id": "en1", "title": "English canonical", "authors": ["A"], "year": 2025, "journal": "J", "doi": "10.1000/en1", "url": "https://doi.org/10.1000/en1"}]
    registry = {"schema_version": 1, "as_of": "2026-10-18", "topics": [{"id": "reviews", "label": "综述"}], "entries": [
        {"id": "zh1", "category": "chinese_original", "topic": "reviews", "reference": {"title": "中文原文", "authors": ["B"], "year": 2024, "journal": "中文期刊", "doi": "10.1000/zh1", "url": "https://example.org/zh1"}, "authors_basis": [{"name": "B", "role": "first", "institution": "某大学", "region": "中国内地", "source_url": "https://example.org/evidence", "locator": "作者单位 1"}], "language_evidence": {"source_url": "https://example.org/evidence", "locator": "期刊页面语言", "note": "页面为中文原文"}, "why_read": "w", "practice": "p", "caution": "c"},
        {"id": "en-entry", "category": "team_english", "topic": "reviews", "paper_id": "en1", "authors_basis": [{"name": "A", "role": "corresponding", "institution": "某大学", "region": "中国香港", "source_url": "https://example.org/evidence2", "locator": "affiliation 1"}], "why_read": "w", "practice": "p", "caution": "c"},
    ]}
    return registry, papers, {"papers": {"en1": {"title": "English canonical", "title_zh": "中文参考译名", "doi": "10.1000/en1"}}}


def canonical_chinese_fixture():
    registry, papers, titles = fixture()
    papers.append({
        "id": "zh-canonical",
        "title": "中文规范标题",
        "authors": ["B"],
        "year": 2024,
        "journal": "中文期刊",
        "doi": "10.1000/zh-canonical",
        "url": "https://doi.org/10.1000/zh-canonical",
        "private_pdf_path": "private/should-never-render.pdf",
    })
    titles["papers"]["zh-canonical"] = {
        "title": "中文规范标题",
        "title_zh": "中文规范标题（译名）",
        "doi": "10.1000/zh-canonical",
    }
    registry["entries"].append({
        "id": "zh-canonical-entry",
        "category": "chinese_original",
        "topic": "reviews",
        "paper_id": "zh-canonical",
        "authors_basis": [{
            "name": "B", "role": "first", "institution": "某大学",
            "region": "中国内地", "source_url": "https://example.org/evidence3",
            "locator": "中文期刊作者单位",
        }],
        "language_evidence": {
            "source_url": "https://example.org/evidence3",
            "locator": "中文正文",
            "note": "页面为中文原文",
        },
        "why_read": "w", "practice": "p", "caution": "c",
    })
    return registry, papers, titles


def route_for(registry, papers, titles):
    """Make a small authoritative route fixture for domestic rendering tests."""
    registry = copy.deepcopy(registry); papers = copy.deepcopy(papers); titles = copy.deepcopy(titles)
    zh = registry["entries"][0]
    ref = zh.pop("reference")
    ref["id"] = "zh1"
    papers.append(ref)
    titles["papers"]["zh1"] = {"title": ref["title"], "title_zh": ref["title"], "doi": ref["doi"]}
    zh["paper_id"] = "zh1"
    route = {
        "stages": [{"id": stage, "label": stage} for stage in ("baseline", "beginner", "intermediate", "frontier")],
        "frontiers": [{"id": "f1", "label": "方向一"}, {"id": "f2", "label": "方向二"}],
        "papers": {
            "zh1": {"stage": "baseline", "frontiers": ["f1", "f2"]},
            "zh-canonical": {"stage": "frontier", "frontiers": ["f1"]},
        },
    }
    return registry, papers, titles, route


class DomesticPapersTests(unittest.TestCase):
    def test_validate_and_prerender_both_groups(self):
        registry, papers, titles = fixture()
        rows = builder.validate(registry, papers, titles)
        page = builder.build(registry, papers, titles)
        self.assertEqual(len(rows), 2)
        self.assertIn("中文期刊 / 中文原文", page)
        self.assertIn("国内团队英文论文", page)
        self.assertIn("中文原文", page)

    def test_rejects_unknown_id_duplicate_doi_missing_language_and_private_fields(self):
        registry, papers, titles = fixture()
        bad = copy.deepcopy(registry); bad["entries"][1]["paper_id"] = "missing"
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)
        bad = copy.deepcopy(registry); bad["entries"][0]["reference"]["doi"] = "10.1000/en1"
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)
        bad = copy.deepcopy(registry); del bad["entries"][0]["language_evidence"]
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)
        bad = copy.deepcopy(registry); bad["entries"][0]["private_path"] = "x"
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)

    def test_rejects_unsafe_evidence_and_name_only_role(self):
        registry, papers, titles = fixture()
        # Assemble this deliberately invalid fixture rather than publishing a
        # signed-looking URL literal; no real authorization value is involved.
        bad = copy.deepcopy(registry); bad["entries"][0]["authors_basis"][0]["source_url"] = "?".join(("https://fixture.invalid/", "token=fixture"))
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)
        bad = copy.deepcopy(registry); bad["entries"][0]["authors_basis"][0]["role"] = "author"
        with self.assertRaises(ValueError): builder.validate(bad, papers, titles)

    def test_rejects_missing_metadata_and_title_map(self):
        registry, papers, titles = fixture()
        for mutate in (
            lambda r: r["entries"][0]["reference"].pop("doi"),
            lambda r: r["entries"][0]["reference"].update(year="2024"),
            lambda r: r["entries"][0]["reference"].update(journal=""),
            lambda r: r["entries"][0]["language_evidence"].update(locator=""),
            lambda r: r["entries"][0]["authors_basis"][0].update(institution=""),
            lambda r: r["entries"][0]["authors_basis"][0].update(region="海外"),
        ):
            bad = copy.deepcopy(registry); mutate(bad)
            with self.assertRaises(ValueError): builder.validate(bad, papers, titles)
        with self.assertRaises(ValueError): builder.validate(registry, papers, {"papers": {}})

    def test_escapes_injected_html(self):
        registry, papers, titles = fixture(); registry["entries"][0]["why_read"] = '<script>alert(1)</script>'
        page = builder.build(registry, papers, titles)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_new_screening_and_modeling_topics_are_registered_and_rendered(self):
        root = Path(__file__).parents[1]
        registry = json.loads((root / "data" / "domestic_papers.json").read_text(encoding="utf-8"))
        papers = json.loads((root / "data" / "papers.json").read_text(encoding="utf-8"))
        titles = json.loads((root / "data" / "paper_titles_zh.json").read_text(encoding="utf-8"))
        topic_ids = {topic["id"] for topic in registry["topics"]}
        self.assertTrue({"electrode_screening", "electrochem_modeling"} <= topic_ids)
        for topic in ("electrode_screening", "electrochem_modeling"):
            self.assertTrue(any(entry["topic"] == topic for entry in registry["entries"]))
        page = builder.build(registry, papers, titles)
        self.assertIn('value="electrode_screening"', page)
        self.assertIn('value="electrochem_modeling"', page)
        self.assertIn('data-topic="electrode_screening"', page)
        self.assertIn('data-topic="electrochem_modeling"', page)

    def test_six_release_entries_are_canonical_and_p7_affiliation_is_pdf_checked(self):
        root = Path(__file__).parents[1]
        registry = json.loads((root / "data" / "domestic_papers.json").read_text(encoding="utf-8"))
        papers = json.loads((root / "data" / "papers.json").read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in registry["entries"]}
        canonical_ids = {
            "wang2025_battery_ml_paradigms", "wang2024_mlip_scaling_review",
            "geng2025_vaspkit_protocol", "wang2021_vaspkit", "zhang2018_deep_potential",
            "recent_10_1038_s41524-025-01623-4", "wang2025_dpa_sse", "you2024_llzo_pca_deepmd",
            "qi2024_lgps_ml_aimd", "zhang2024_mlmd_size_conductivity", "tan2026_pemd",
            "recent_10_1038_s41467-025-67982-0", "recent_10_1038_s41524-025-01747-7",
            "recent_10_1038_s41524-025-01615-4", "recent_10_1038_s41467-025-62824-5",
            "cn_10_19799_j_cnki_2095-4239_2022_0504", "cn_10_14062_j_issn_0454-5648_20220818",
            "cn_10_19799_j_cnki_2095-4239_2022_0051", "cn_10_19799_j_cnki_2095-4239_2024_0586",
            "cn_aps2025_liquid", "cn_aps2024_vs2", "cn_aps2026_ml_dft", "cn_shen2020_polymer",
            "cn_chen2024_mlmd_nucleation", "hu2025_lmfp_active_learning", "tang2022_2d_anode_screening",
            "dou2024_li_alloy_sei", "ma2022_3d_electrochemical_thermal_lithium",
            "yang2023_electrochemical_thermal_component", "li2024_phase_field_dendrite",
            "cn_shi2023_oxygen_vacancy_clusters", "cn_li2024_latp_migration", "cn_li2025_latp_surface",
            "cn_you2021_lipon_li_interface", "cn_zhong2021_rare_earth_lfp", "cn_shen2021_si_graphene",
            "cn_he2022_halide_cation", "cn_wang2022_ligand_field", "cn_xu2024_big_data_design",
        }
        paper_ids = {paper["id"] for paper in papers}
        self.assertEqual(len(registry["entries"]), 39)
        self.assertEqual({entry["paper_id"] for entry in registry["entries"]}, canonical_ids)
        self.assertTrue(canonical_ids <= paper_ids)
        self.assertEqual(sum(entry["category"] == "chinese_original" for entry in registry["entries"]), 20)
        self.assertEqual(sum(entry["category"] == "team_english" for entry in registry["entries"]), 19)
        self.assertTrue(all("reference" not in entry for entry in registry["entries"]))
        p7 = entries["cn_10_19799_j_cnki_2095-4239_2023_0082"]
        self.assertEqual(p7["authors_basis"][0]["institution"], "上海工程技术大学机械与汽车工程学院")

    def test_canonical_chinese_entry_renders_from_metadata_without_private_pdf(self):
        registry, papers, titles = canonical_chinese_fixture()
        rows = builder.validate(registry, papers, titles)
        page = builder.build(registry, papers, titles)
        self.assertEqual(rows[-1]["canonical"], True)
        self.assertIn("中文规范标题", page)
        self.assertIn("主库记录", page)
        self.assertNotIn("private/should-never-render.pdf", page)
        self.assertNotIn("private_pdf_path", page)
        self.assertNotIn(".pdf", page.lower())

    def test_exact_software_and_functional_metadata_is_not_inferred(self):
        catalog = json.loads((Path(__file__).parents[1] / "data" / "papers.json").read_text(encoding="utf-8"))
        by_doi = {paper["doi"]: paper for paper in catalog}
        pw91 = by_doi["10.7498/aps.70.20210227"]
        rescu = by_doi["10.7498/aps.72.20222300"]
        cast = by_doi["10.7498/aps.70.20210521"]
        self.assertIn("PW91", pw91["methods"])
        self.assertNotIn("PBE", pw91["methods"])
        self.assertIn("RESCU", rescu["methods"])
        self.assertNotIn("VASP", rescu["methods"])
        self.assertIn("CASTEP", cast["methods"])
        self.assertNotIn("Materials Studio", cast["methods"])
        self.assertNotIn("MS", cast["methods"])

    def test_authoritative_route_groups_chinese_once_and_crosslinks_frontiers(self):
        registry, papers, titles = canonical_chinese_fixture()
        registry, papers, titles, route = route_for(registry, papers, titles)
        page = builder.build(registry, papers, titles, route=route)
        self.assertEqual(page.count('class="domestic-card"'), 3)  # 2 Chinese + 1 English
        self.assertEqual(page.count('class="domestic-stage"'), 4)
        self.assertEqual(page.count('class="domestic-frontier-group"'), 2)
        self.assertEqual(page.count('class="domestic-frontier-link"'), 3)
        self.assertIn('data-stage="frontier"', page)
        self.assertIn('>baseline</a>', page)

    def test_authoritative_route_rejects_unmapped_or_unknown_chinese(self):
        registry, papers, titles = canonical_chinese_fixture()
        registry, papers, titles, route = route_for(registry, papers, titles)
        del route["papers"]["zh1"]
        with self.assertRaises(ValueError): builder.build(registry, papers, titles, route=route)
        registry, papers, titles, route = route_for(*canonical_chinese_fixture())
        route["papers"]["zh1"]["stage"] = "not-a-stage"
        with self.assertRaises(ValueError): builder.build(registry, papers, titles, route=route)
        registry, papers, titles, route = route_for(*canonical_chinese_fixture())
        route["papers"]["zh1"]["frontiers"] = ["not-a-frontier"]
        with self.assertRaises(ValueError): builder.build(registry, papers, titles, route=route)


if __name__ == "__main__": unittest.main()
