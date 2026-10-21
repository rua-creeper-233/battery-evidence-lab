"""Shared, idempotent chrome for the local app and its static publication."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


PUBLIC_BASE = "https://rua-creeper-233.github.io/battery-evidence-lab/"
REPOSITORY_URL = "https://github.com/rua-creeper-233/battery-evidence-lab"
PAGES = {
    "index.html": ("Battery Evidence Lab", "检索电池材料计算论文，查阅 DFT、MD、机器学习势的知识、操作流程与来源。"),
    "future-directions.html": ("未来方向 · Battery Evidence Lab", "从电池材料计算综述中选择研究问题，查看对应论文、复现任务与验证方法。"),
    "ai-battery-applications.html": ("AI 应用 · Battery Evidence Lab", "AI 在电池材料模拟中的应用场景、论文进展、数据与实现路径。"),
    "foundations.html": ("基础地图 · Battery Evidence Lab", "电池材料计算需要的数学、物理、DFT、MD 与电化学基础及参考书目。"),
    "learning-route.html": ("学习路线 · Battery Evidence Lab", "按 baseline、入门、进阶和前沿专题查阅论文与科研练习。"),
    "domestic-papers.html": ("国内论文 · Battery Evidence Lab", "分别查阅中文论文与中国团队的英文论文，以及对应的材料计算学习路线。"),
}
NAV = (
    ("index.html#research-question", "证据问答", "research-question"),
    ("index.html#library", "论文库", "library"),
    ("index.html#tutorials", "教程", "tutorials"),
    ("future-directions.html", "未来方向", ""),
    ("ai-battery-applications.html", "AI 应用", ""),
    ("foundations.html", "基础地图", ""),
    ("learning-route.html", "学习路线", ""),
    ("domestic-papers.html", "国内论文", ""),
)


def navigation(page: str) -> str:
    home = page == "index.html"
    tabs, links = [], []
    for target, label, panel in NAV:
        if home and panel:
            selected = panel == "research-question"
            tabs.append(
                f'<a href="#{panel}" id="tab-{panel}" role="tab" '
                f'aria-controls="{panel}" aria-selected="{str(selected).lower()}" '
                f'tabindex="{0 if selected else -1}" data-home-tab="{panel}">{label}</a>'
            )
        else:
            current = ' aria-current="page"' if target == page else ""
            links.append(f'<a href="./{target}"{current}>{label}</a>')
    tab_group = '<div class="home-tabs" role="tablist" aria-label="首页工具">' + "".join(tabs) + "</div>" if home else ""
    return (
        '<nav class="site-nav" aria-label="页面导航">'
        '<a class="brand" href="./index.html#research-question">Battery Evidence Lab</a>'
        f'<div class="site-nav-links">{tab_group}{"".join(links)}</div></nav>'
    )


class _AuthorStyleValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'style':
            self.inside = True
            self.parts = []

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != 'style' or not self.inside:
            return
        css = re.sub(r'/\*.*?\*/', '', ''.join(self.parts), flags=re.S)
        if re.search(r':root\b', css):
            raise ValueError('Page styles must use the shared design tokens, not declare :root')
        self.inside = False


def prepare_chrome(source: str, page: str, shared_css: str) -> str:
    """Normalize authored/generated pages without touching their app scripts."""
    if page not in PAGES:
        raise ValueError("unknown public page")
    source = re.sub(r'<style\b[^>]*\bdata-lab-ui-inline\b[^>]*>.*?</style>', '<link rel="stylesheet" href="./lab-ui.css">', source, flags=re.S)
    # Fail on a second theme rather than silently rewriting authored CSS.
    _AuthorStyleValidator().feed(source)
    css = re.sub(r"</style", lambda _: r"<\/style", shared_css, flags=re.I)
    style = f'<style data-lab-ui-inline>{css}</style>'
    # Replace (rather than also request) the shared stylesheet, retaining order
    # before the home and battery-specific assets.
    shared_link = r'<link\b(?=[^>]*href=[\"\']\./lab-ui\.css[\"\'])[^>]*>'
    if re.search(shared_link, source):
        source = re.sub(shared_link, lambda _: style, source, count=1)
    else:
        source = source.replace("</head>", style + "</head>", 1)
    source = re.sub(r'<nav\b[^>]*class="site-nav"[^>]*>.*?</nav>', lambda _: navigation(page), source, count=1, flags=re.S)
    if page == "index.html":
        source = re.sub(
            r'<(section|aside)\b([^>]*\bdata-home-panel="(research-question|library|tutorials)"[^>]*)>',
            lambda m: f'<{m[1]}' + re.sub(r'\s+(?:role|aria-labelledby|tabindex)="[^"]*"', '', m[2])
            + f' role="tabpanel" aria-labelledby="tab-{m[3]}" tabindex="0">',
            source,
        )
    title, description = PAGES[page]
    source = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", source, count=1, flags=re.S)
    source = re.sub(r'<meta\b(?=[^>]*(?:name="(?:description|twitter:card)"|property="og:[^"]+"))[^>]*>', '', source)
    source = re.sub(r'<link\b(?=[^>]*rel="(?:canonical|icon)")[^>]*>', '', source)
    url = PUBLIC_BASE + page
    metadata = (
        f'<meta name="description" content="{html.escape(description, quote=True)}">'
        f'<meta property="og:title" content="{html.escape(title, quote=True)}">'
        f'<meta property="og:description" content="{html.escape(description, quote=True)}">'
        f'<meta property="og:type" content="website"><meta property="og:url" content="{url}">'
        f'<meta property="og:image" content="{PUBLIC_BASE}share-card.png">'
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<link rel="canonical" href="{url}"><link rel="icon" type="image/svg+xml" href="./favicon.svg">'
    )
    source = source.replace("</head>", metadata + "</head>", 1)
    source = re.sub(r'<footer\b[^>]*\bdata-site-footer\b[^>]*>.*?</footer>\s*', '', source, flags=re.S)
    # Per-page source links stay with their content; only the global chrome is a
    # footer. Converting them once makes successive builds stable.
    source = re.sub(r'<footer\b[^>]*>(.*?)</footer>', r'<section class="page-sources">\1</section>', source, flags=re.S)
    footer = (
        '<footer class="site-footer" data-site-footer><span>Battery Evidence Lab</span>'
        '<a href="./guides/PROJECT_STATUS.md">项目记录</a>'
        f'<a href="{REPOSITORY_URL}" target="_blank" rel="noopener noreferrer">源码（私有）</a>'
        '</footer>'
    )
    source = re.sub(r'<script\b[^>]*src="\./nav-overflow\.js"[^>]*></script>', '', source)
    source = source.replace("</body>", footer + '<script src="./nav-overflow.js" defer></script></body>', 1)
    parts = re.split(r"(<script\b[^>]*>.*?</script>|<pre\b[^>]*>.*?</pre>)", source, flags=re.S)
    return "".join(part if i % 2 else re.sub(r"(?m)^[ \t]+(?=\r?$)", "", part) for i, part in enumerate(parts))
