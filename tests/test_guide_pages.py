import html as html_lib
import re
import unittest
from pathlib import Path

from tools.build_guides import GUIDE_PAGES, build, rewrite_guide_links

ROOT = Path(__file__).resolve().parents[1]


class GuidePagesTest(unittest.TestCase):
    def test_markdown_links_resolve_from_guide_source_directory(self):
        rendered = build("# Guide\n\n[record](PROJECT_STATUS.md) [route](../learning-route.html#stage-baseline) [agent](AGENT_IMPLEMENTATION_GUIDE.md#section)\n", "research-roadmap.html")
        self.assertIn('href="./guides/PROJECT_STATUS.md"', rendered)
        self.assertIn('href="./learning-route.html#stage-baseline"', rendered)
        self.assertIn('href="./agent-guide.html#section"', rendered)
        self.assertNotIn('href="./guides/agent-guide.html', rendered)

    def test_rewriting_preserves_fragment_and_external_documents(self):
        source = '[jump](AGENT_IMPLEMENTATION_GUIDE.md#one) [other](https://example.org/AGENT_IMPLEMENTATION_GUIDE.md)'
        result = rewrite_guide_links(source)
        self.assertIn('(./agent-guide.html#one)', result)
        self.assertIn('(https://example.org/AGENT_IMPLEMENTATION_GUIDE.md)', result)
        code = '<script>const sample = \'<a href="./guides/AGENT_IMPLEMENTATION_GUIDE.md">x</a>\';</script>'
        self.assertEqual(rewrite_guide_links(code), code)

    def test_page_map_and_cross_links(self):
        self.assertEqual(set(GUIDE_PAGES), {"agent-guide.html", "research-roadmap.html"})
        source = "[agent](AGENT_IMPLEMENTATION_GUIDE.md) [road](BATTERY_RESEARCH_ROADMAP_20260918.md)"
        rewritten = rewrite_guide_links(source)
        self.assertIn("./agent-guide.html", rewritten)
        self.assertIn("./research-roadmap.html", rewritten)
        self.assertEqual(rewrite_guide_links("```md\n[x](AGENT_IMPLEMENTATION_GUIDE.md)\n```"), "```md\n[x](AGENT_IMPLEMENTATION_GUIDE.md)\n```")
        old_html = '<a href="./guides/AGENT_IMPLEMENTATION_GUIDE.md#start">guide</a><pre><a href="./guides/AGENT_IMPLEMENTATION_GUIDE.md">code</a></pre>'
        rewritten_html = rewrite_guide_links(old_html)
        self.assertIn('href="./agent-guide.html#start"', rewritten_html)
        self.assertIn('href="./guides/AGENT_IMPLEMENTATION_GUIDE.md">code', rewritten_html)

    def test_safety_and_toc(self):
        source = """# Title
## A section
### A subsection
<script>alert(1)</script>

[bad](javascript:alert(1)) [data](data:text/html,x) [good](https://example.com)

```html
<script>alert(2)</script>
[not a link](https://example.com)
```
"""
        rendered = build(source, "agent-guide.html")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn('href="https://example.com"', rendered)
        self.assertNotIn('href="javascript:', rendered.lower())
        self.assertNotIn('href="data:', rendered.lower())
        self.assertNotIn("javascript", build("[x](%6aavascript:alert(1))", "agent-guide.html").lower())
        self.assertEqual(len(re.findall(r"<h1(?:\s|>)", rendered)), 1)
        ids = set(re.findall(r'<h[2-4] id="([^"]+)"', rendered))
        toc_ids = set(re.findall(r'<li class="toc-level-\d"><a href="#([^"]+)"', rendered))
        self.assertTrue(ids)
        self.assertTrue(toc_ids <= ids)
        code = re.search(r"<pre><code[^>]*>(.*?)</code></pre>", rendered, re.S).group(1)
        self.assertNotIn("<script>", code)
        self.assertIn("&lt;script&gt;", code)
        self.assertNotIn("<a ", code)

    def test_real_guides_render(self):
        for page, source_name in GUIDE_PAGES.items():
            source = (ROOT / "guides" / source_name).read_text(encoding="utf-8")
            rendered = build(source, page)
            self.assertIn("<!doctype html>", rendered)
            self.assertIn(f'./guides/{source_name}', html_lib.unescape(rendered))
            self.assertIn("class=\"guide-toc\"", rendered)
            self.assertEqual(len(re.findall(r"<h1(?:\s|>)", rendered)), 1)


if __name__ == "__main__":
    unittest.main()
