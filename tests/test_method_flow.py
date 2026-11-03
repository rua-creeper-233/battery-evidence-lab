"""Focused invariants for the shared method-flow injection."""

import unittest

from method_flow import method_flow, prepare_method_flow


class MethodFlowTests(unittest.TestCase):
    def test_injects_only_supported_pages_and_is_idempotent(self):
        foundations = '<main><p>existing</p></main>'
        first = prepare_method_flow(foundations, 'foundations.html')
        second = prepare_method_flow(first, 'foundations.html')
        self.assertEqual(first, second)
        self.assertEqual(first.count('data-method-flow'), 1)
        self.assertTrue(first.index('data-method-flow') > first.index('<main>'))
        route = prepare_method_flow('<main><p>route</p></main>', 'learning-route.html')
        self.assertEqual(route.count('data-method-flow'), 1)
        self.assertIn('foundations.html#topic-ks', route)
        self.assertIn('foundations.html#topic-md', route)
        self.assertIn('foundations.html#topic-mlip', route)
        other = '<main><p>other</p></main>'
        self.assertEqual(prepare_method_flow(other, 'index.html'), other)

    def test_removes_only_existing_method_flow_and_preserves_unrelated_sections(self):
        source = '<main><section data-method-flow><p>old</p></section><section data-other-flow>keep</section><section>keep too</section></main>'
        result = prepare_method_flow(source, 'foundations.html')
        self.assertEqual(result.count('data-method-flow'), 1)
        self.assertIn('data-other-flow', result)
        self.assertIn('keep too', result)
        self.assertEqual(result.count('>DFT<'), 1)

    def test_flow_contract_has_three_methods_and_valid_foundations_anchors(self):
        flow = method_flow()
        self.assertEqual(flow.count('class="method-flow__node"'), 3)
        self.assertEqual(flow.count('href="./foundations.html#'), 3)
        for anchor in ('topic-ks', 'topic-md', 'topic-mlip'):
            self.assertIn(anchor, flow)
        self.assertIn('data-method-flow', flow)


if __name__ == '__main__':
    unittest.main()
