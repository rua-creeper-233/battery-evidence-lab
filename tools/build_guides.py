"""Render the two public Markdown guides as safe, self-contained HTML pages."""
from __future__ import annotations

import html
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

GUIDE_PAGES = {
    "agent-guide.html": "AGENT_IMPLEMENTATION_GUIDE.md",
    "research-roadmap.html": "BATTERY_RESEARCH_ROADMAP_20260918.md",
}


def _guide_target(target: str) -> str | None:
    target = target.strip()
    if not target or any(ord(c) < 32 for c in target) or "\\" in target:
        return None
    decoded = unquote(target)
    if "%" in target and decoded != target:
        return None
    if target.startswith("//"):
        return None
    parts = urlsplit(target)
    if parts.scheme:
        if parts.scheme.lower() != "https" or not parts.netloc or parts.username or parts.password:
            return None
        return target
    if parts.netloc or target.startswith("/"):
        return None
    path = parts.path
    if path.startswith("#") or not path:
        return target
    # Resolve Markdown links as if they originated in the guides/ directory.
    resolved = posixpath.normpath(posixpath.join("guides", path))
    if resolved != "guides" and (resolved == ".." or resolved.startswith("../")):
        return None
    if resolved.startswith("guides/"):
        name = posixpath.basename(resolved)
        fragment = f"#{parts.fragment}" if parts.fragment else ""
        if name == "AGENT_IMPLEMENTATION_GUIDE.md": return "./agent-guide.html" + fragment
        if name == "BATTERY_RESEARCH_ROADMAP_20260918.md": return "./research-roadmap.html" + fragment
        return "./" + resolved + (f"?{parts.query}" if parts.query else "") + fragment
    return "./" + resolved + (f"?{parts.query}" if parts.query else "") + (f"#{parts.fragment}" if parts.fragment else "")


def _slug(text: str, used: set[str]) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.lower()).strip("-") or "section"
    base = slug
    n = 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def _inline(text: str) -> str:
    tokens: dict[str, str] = {}
    def token(value: str) -> str:
        key = f"\x00{len(tokens)}\x00"
        tokens[key] = value
        return key
    text = re.sub(r"`([^`\n]+)`", lambda m: token(f"<code>{html.escape(m.group(1))}</code>"), text)
    def link(m: re.Match[str]) -> str:
        href = _guide_target(m.group(2))
        if href is None:
            return m.group(0)
        return token(f'<a href="{html.escape(href, quote=True)}">{html.escape(m.group(1))}</a>')
    text = re.sub(r"\[([^]\n]+)\]\(([^)\s]+)\)", link, text)
    rendered = html.escape(text)
    rendered = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", rendered)
    for key, value in tokens.items():
        rendered = rendered.replace(html.escape(key), value)
    return rendered


def rewrite_guide_links(source: str) -> str:
    """Rewrite guide links in Markdown or old generated HTML, excluding code."""
    def rewrite_target(target: str) -> str:
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            return target
        path = parts.path.removeprefix("./")
        for page, filename in GUIDE_PAGES.items():
            if path in {filename, "guides/" + filename}:
                return "./" + page + ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")
        return target

    protected = r"(```[^\n]*\n.*?```[^\S\n]*(?:\n|$)|<pre\b[^>]*>.*?</pre>|<code\b[^>]*>.*?</code>|<script\b[^>]*>.*?</script>)"
    chunks = re.split(protected, source, flags=re.I | re.S)
    for i in range(0, len(chunks), 2):
        chunks[i] = re.sub(
            r"(\[[^]\n]+\]\()([^\s)]+)(\))",
            lambda m: m[1] + rewrite_target(m[2]) + m[3], chunks[i],
        )
        chunks[i] = re.sub(
            r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])(?P<target>[^\"']*)(?P=quote)",
            lambda m: m["prefix"] + m["quote"] + rewrite_target(m["target"]) + m["quote"],
            chunks[i], flags=re.I,
        )
    return "".join(chunks)


def _cells(line: str) -> list[str]:
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def build(markdown: str, page: str) -> str:
    if page not in GUIDE_PAGES:
        raise ValueError(f"unknown guide page: {page}")
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    used: set[str] = set()
    i = 0
    h1_seen = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            language = line[3:].strip().split()[0] if line[3:].strip() else ""
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i]); i += 1
            if i < len(lines): i += 1
            cls = f' class="language-{html.escape(language, quote=True)}"' if language else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(code))}</code></pre>")
            continue
        hm = re.match(r"^\s*(#{1,4})\s+(.+?)\s*#*\s*$", line)
        if hm:
            level = len(hm.group(1)); title = re.sub(r"[`*_]", "", hm.group(2)).strip()
            if level == 1 and h1_seen: level = 2
            first_h1 = level == 1 and not h1_seen
            if level == 1: h1_seen = True
            ident = _slug(title, used)
            headings.append((level, title, ident))
            # The document title is rendered once in the hero below; keep its
            # id in the heading map but avoid producing a second h1 in content.
            if not first_h1:
                out.append(f'<h{level} id="{ident}">{_inline(hm.group(2))}</h{level}>')
            i += 1; continue
        if i + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[i + 1]):
            heads = _cells(line); i += 2; rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip(): rows.append(_cells(lines[i])); i += 1
            out.append('<div class="guide-table-wrap" tabindex="0" aria-label="可横向滚动的表格"><table><thead><tr>' + ''.join(f'<th scope="col">{_inline(c)}</th>' for c in heads) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>')
            continue
        lm = re.match(r"^\s*([-+*]|\d+[.)])\s+(.+)$", line)
        if lm:
            ordered = lm.group(1)[0].isdigit(); tag = "ol" if ordered else "ul"; items = []
            while i < len(lines):
                mm = re.match(r"^\s*([-+*]|\d+[.)])\s+(.+)$", lines[i])
                if not mm or mm.group(1)[0].isdigit() != ordered: break
                items.append(f"<li>{_inline(mm.group(2))}</li>"); i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>"); continue
        if re.match(r"^\s*> ?", line):
            quote = []
            while i < len(lines) and re.match(r"^\s*> ?", lines[i]): quote.append(re.sub(r"^\s*> ?", "", lines[i])); i += 1
            out.append('<blockquote>' + '<p>' + _inline(" ".join(quote)) + '</p></blockquote>'); continue
        if not line.strip(): i += 1; continue
        para = [line]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#{1,4})\s+|^\s*([-+*]|\d+[.)])\s+|^\s*> ?|^```", lines[i]): para.append(lines[i]); i += 1
        out.append("<p>" + _inline(" ".join(para)) + "</p>")
    title = next((t for l, t, _ in headings if l == 1), page.removesuffix(".html").replace("-", " ").title())
    other = "research-roadmap.html" if page == "agent-guide.html" else "agent-guide.html"
    toc = ''.join(f'<li class="toc-level-{level}"><a href="#{ident}">{html.escape(title)}</a></li>' for level, title, ident in headings if level > 1)
    source = GUIDE_PAGES[page]
    other_label = "电池研究路线图" if page == "agent-guide.html" else "工具 Agent 使用指南"
    hero_id = next((ident for level, _, ident in headings if level == 1), "guide-title")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)} · Battery Evidence Lab</title><link rel="stylesheet" href="./lab-ui.css"><link rel="stylesheet" href="./guide.css"><script src="./lab-ui.js" defer></script></head><body><div class="shell guide-page"><nav class="site-nav" aria-label="页面导航"></nav><header class="guide-hero"><p class="guide-kicker">Battery Evidence Lab · 指南</p><h1 id="{hero_id}">{html.escape(title)}</h1><div class="guide-meta"><a href="./guides/{html.escape(source, quote=True)}" download>下载 Markdown 源文</a><a href="./{other}">阅读{other_label}</a></div></header><div class="guide-layout"><aside class="guide-toc" aria-label="章节目录"><details open><summary>本页目录</summary><ol>{toc}</ol></details></aside><main class="guide-content">{''.join(out)}</main></div></div></body></html>'''
