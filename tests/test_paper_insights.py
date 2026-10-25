import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("validator", Path(__file__).parents[1] / "validate_paper_insights.py")
validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)

def good():
    return {"schema_version":1,"as_of":"2026-10-25","methodology":{"reference_title":"Cai et al.","reference_url":"https://doi.org/10.1234/ref","implemented_layers":"L1-L4","note":"Public reading aid."},"papers":{"cai-2024":{"paper_id":"cai-2024","doi":"10.1234/example","sources":[{"id":"s1","url":"https://doi.org/10.1234/example","scope":"article","locator":"Abstract"}],"sections":{"findings":[{"text":"A reported finding.","source_refs":["s1"],"kind":"reported"}]},"relations":[]}}}

class PaperInsightsValidationTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(validator.validate(good()), [])
    def test_conditions_keep_claim_provenance(self):
        value = good()
        value['papers']['cai-2024']['sections']['conditions'] = [{'text':'The reported cell condition.','source_refs':['s1'],'kind':'reported'}]
        self.assertEqual(validator.validate(value), [])
        value['papers']['cai-2024']['sections']['conditions'][0]['source_refs'] = ['unknown']
        self.assertTrue(validator.validate(value))
    def test_unknown_private_field_fails(self):
        value=good(); value["papers"]["cai-2024"]["private_path"]="C:/secret.pdf"; self.assertTrue(validator.validate(value))
    def test_missing_ref_fails(self):
        value=good(); value["papers"]["cai-2024"]["sections"]["findings"][0]["source_refs"]=["missing"]; self.assertTrue(validator.validate(value))
    def test_unknown_canonical_and_wrong_doi(self): self.assertTrue(validator.validate(good(), [{"id":"other","doi":"10.1234/other"}]))
    def test_unknown_catalog_id_is_rejected_even_with_valid_doi(self):
        self.assertTrue(validator.validate(good(), [{"id":"other","doi":"10.1234/example"}]))
    def test_catalog_doi_mismatch_is_rejected_for_known_id(self):
        self.assertTrue(validator.validate(good(), [{"id":"cai-2024","doi":"10.1234/other"}]))
    def test_private_source_url_is_rejected(self):
        value = good(); value["papers"]["cai-2024"]["sources"][0]["url"] = "https://127.0.0.1/private"
        self.assertTrue(validator.validate(value))
    def test_null_paper_is_rejected(self):
        value = good(); value["papers"]["cai-2024"] = None
        self.assertTrue(validator.validate(value))
    def test_malformed_unhashable_and_locator(self):
        value=good(); value["papers"]["cai-2024"]["sources"][0]["id"]=[]; value["papers"]["cai-2024"]["sources"][0]["locator"]=""; self.assertTrue(validator.validate(value))
    def test_methodology_private_field(self):
        value=good(); value["methodology"]["private_path"]="secret"; self.assertTrue(validator.validate(value))

if __name__ == "__main__": unittest.main()
