"""Regression coverage for the 11-paper bibliographic supplement."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from import_zotero_library import build_zotero_item


ROOT = Path(__file__).parents[1]
PAPERS = {
    str(p["id"]): p
    for p in json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8"))
}
TITLES = json.loads((ROOT / "data" / "paper_titles_zh.json").read_text(encoding="utf-8"))["papers"]
ROUTE = json.loads((ROOT / "data" / "learning_route.json").read_text(encoding="utf-8"))


SUPPLEMENT = {
    "grossfield2019_uncertainty_sampling": {
        "doi": "10.33011/livecoms.1.1.5067", "year": 2019, "authors": 6,
        "title": "Best Practices for Quantification of Uncertainty and Sampling Quality in Molecular Simulations [Article v1.0]",
        "first": "Alan Grossfield", "last": "Daniel M. Zuckerman",
    },
    "chodera2016_equilibration_detection": {
        "doi": "10.1021/acs.jctc.5b00784", "year": 2016, "authors": 1,
        "title": "A Simple Method for Automated Equilibration Detection in Molecular Simulations",
        "first": "John D. Chodera", "last": "John D. Chodera",
    },
    "flyvbjerg1989_correlated_error": {
        "doi": "10.1063/1.457480", "year": 1989, "authors": 2,
        "title": "Error estimates on averages of correlated data",
        "first": "H. Flyvbjerg", "last": "H. G. Petersen",
    },
    "lejaeghere2016_dft_reproducibility": {
        "doi": "10.1126/science.aad3000", "year": 2016, "authors": 69,
        "title": "Reproducibility in density functional theory calculations of solids",
        "first": "Kurt Lejaeghere", "last": "Stefaan Cottenier",
    },
    "bosoni2024_dft_precision_workflows": {
        "doi": "10.1038/s42254-023-00655-3", "year": 2024, "authors": 45,
        "title": "How to verify the precision of density-functional-theory implementations via reproducible and universal workflows",
        "first": "Emanuele Bosoni", "last": "Giovanni Pizzi",
    },
    "wilkinson2016_fair_principles": {
        "doi": "10.1038/sdata.2016.18", "year": 2016, "authors": 53,
        "title": "The FAIR Guiding Principles for scientific data management and stewardship",
        "first": "Mark D. Wilkinson", "last": "Barend Mons",
    },
    "hohenberg1964_inhomogeneous_electron_gas": {
        "doi": "10.1103/PhysRev.136.B864", "year": 1964, "authors": 2,
        "title": "Inhomogeneous Electron Gas", "first": "P. Hohenberg", "last": "W. Kohn",
    },
    "kohn1965_self_consistent_dft": {
        "doi": "10.1103/PhysRev.140.A1133", "year": 1965, "authors": 2,
        "title": "Self-Consistent Equations Including Exchange and Correlation Effects",
        "first": "W. Kohn", "last": "L. J. Sham",
    },
    "verlet1967_classical_fluids": {
        "doi": "10.1103/PhysRev.159.98", "year": 1967, "authors": 1,
        "title": "Computer \"Experiments\" on Classical Fluids. I. Thermodynamical Properties of Lennard-Jones Molecules",
        "first": "Loup Verlet", "last": "Loup Verlet",
    },
    "nose1984_constant_temperature_md": {
        "doi": "10.1063/1.447334", "year": 1984, "authors": 1,
        "title": "A unified formulation of the constant temperature molecular dynamics methods",
        "first": "Shuichi Nosé", "last": "Shuichi Nosé",
    },
    "hoover1985_canonical_dynamics": {
        "doi": "10.1103/PhysRevA.31.1695", "year": 1985, "authors": 1,
        "title": "Canonical dynamics: Equilibrium phase-space distributions",
        "first": "William G. Hoover", "last": "William G. Hoover",
    },
}


class SupplementCatalogTests(unittest.TestCase):
    def test_all_supplement_records_have_canonical_metadata_and_baseline_route(self):
        baseline_ids = {
            str(pid)
            for stage in ROUTE["stages"] if stage["id"] == "baseline"
            for pid in stage["paper_ids"]
        }
        for paper_id, expected in SUPPLEMENT.items():
            with self.subTest(paper_id=paper_id):
                paper = PAPERS[paper_id]
                self.assertEqual(paper["doi"], expected["doi"])
                self.assertEqual(paper["year"], expected["year"])
                self.assertEqual(paper["title"], expected["title"])
                self.assertEqual(len(paper["authors"]), expected["authors"])
                self.assertEqual(paper["authors"][0], expected["first"])
                self.assertEqual(paper["authors"][-1], expected["last"])
                self.assertIn(paper_id, baseline_ids)
                self.assertEqual(TITLES[paper_id]["doi"], expected["doi"])
                self.assertTrue(TITLES[paper_id]["title_zh"].strip())

    def test_canonical_author_fields_survive_a_clean_export(self):
        for paper_id in SUPPLEMENT:
            with self.subTest(paper_id=paper_id):
                paper = PAPERS[paper_id]
                details = paper["author_details"]
                item = build_zotero_item(paper, "fixture")
                self.assertEqual(len(details), len(paper["authors"]))
                self.assertEqual(
                    item["creators"],
                    [{"creatorType": "author", "firstName": a["given"], "lastName": a["family"]} for a in details],
                )
        science = PAPERS["lejaeghere2016_dft_reproducibility"]
        self.assertEqual(science["authors"][58:63], [
            "Francesca Tavazza", "Patrik Thunström", "Alexandre Tkatchenko", "Marc Torrent", "David Vanderbilt",
        ])
        self.assertIn("Dal Corso", [a["lastName"] for a in build_zotero_item(science, "fixture")["creators"]])
        for paper_id, article in (("grossfield2019_uncertainty_sampling", "5067"),
                                  ("lejaeghere2016_dft_reproducibility", "aad3000"),
                                  ("wilkinson2016_fair_principles", "160018")):
            self.assertEqual(build_zotero_item(PAPERS[paper_id], "fixture")["pages"], article)


if __name__ == "__main__":
    unittest.main()
