import re
import unittest

from site_chrome import NAV, PAGES, prepare_chrome


class SiteChromeTests(unittest.TestCase):
    def source(self):
        return '<html><head><title>Old</title><style>.tiny{font:700 12px serif}</style><link rel="stylesheet" href="./lab-ui.css"><link rel="stylesheet" href="./home.css"></head><body><nav class="site-nav">old</nav><section id="library" data-home-panel="library"></section><footer>Source links</footer><script>const x = "&lt;safe&gt;";</script></body></html>'

    def test_shared_style_is_single_and_before_home(self):
        result = prepare_chrome(self.source(), 'index.html', ':root {--green:#2e6b50}')
        self.assertEqual(result.count('data-lab-ui-inline'), 1)
        self.assertEqual(result.count(':root'), 1)
        self.assertNotIn('body::before', result)
        self.assertIn('font:700 12px', result)
        self.assertLess(result.index('data-lab-ui-inline'), result.index('./home.css'))
        self.assertIn('const x = "&lt;safe&gt;";', result)

    def test_authored_style_is_validated_not_rewritten(self):
        for declaration in (':root{--green:red}', '@media (max-width:600px){:root{--green:red}}'):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                prepare_chrome(self.source().replace('.tiny{font:700 12px serif}', declaration), 'index.html', ':root{}')
        source = self.source().replace('font:700 12px', 'font:700 10px')
        self.assertIn('font:700 10px', prepare_chrome(source, 'index.html', ':root{}'))

    def test_consistent_navigation_metadata_footer(self):
        for page in PAGES:
            with self.subTest(page=page):
                result = prepare_chrome(self.source(), page, ':root{--ink:black}')
                nav = re.search(r'<nav.*?</nav>', result).group()
                for _, label, _ in NAV:
                    self.assertIn('>' + label + '</a>', nav)
                self.assertEqual(result.count('data-site-footer'), 1)
                self.assertEqual(result.count('rel="canonical"'), 1)
                self.assertEqual(result.count('name="description"'), 1)
                self.assertEqual(result.count('rel="icon"'), 1)
                self.assertIn('property="og:image"', result)
                self.assertIn('content="summary_large_image"', result)
                self.assertEqual(result.count('src="./nav-overflow.js"'), 1)
                self.assertIn('Source links', result)
                self.assertIn('role="tablist"', nav) if page == 'index.html' else self.assertNotIn('role="tab"', nav)

    def test_idempotent(self):
        css = ':root {--green:#2e6b50} .site-nav {display:flex}'
        for page in PAGES:
            first = prepare_chrome(self.source(), page, css)
            self.assertEqual(prepare_chrome(first, page, css), first)

    def test_home_tabs_have_matching_panels(self):
        result = prepare_chrome(self.source(), 'index.html', ':root{}')
        self.assertIn('role="tabpanel" aria-labelledby="tab-library"', result)
        self.assertIn('id="tab-library" role="tab" aria-controls="library"', result)

    def test_blank_lines_are_cleaned_without_rewriting_code(self):
        fragment = '<script>const text = `a\n   \nb`;</script><pre>code\n   \n</pre>'
        source = self.source().replace('</body>', '\n    \n' + fragment + '</body>')
        result = prepare_chrome(source, 'index.html', ':root{}')
        self.assertIn(fragment, result)
        self.assertNotIn('\n    \n', result)


if __name__ == '__main__':
    unittest.main()
