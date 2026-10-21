"""Build the public, evidence-linked 国内论文选读 page.

The registry is intentionally a small public allowlist.  Validation happens
before rendering or writing so malformed editorial data cannot produce a page.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "data" / "domestic_papers.json"
PAPERS_PATH = ROOT / "data" / "papers.json"
TITLE_PATH = ROOT / "data" / "paper_titles_zh.json"
OUT_PATH = ROOT / "static" / "domestic-papers.html"
SAFE_URL = re.compile(r"^https://[^\s<>\"']+$")
TOPICS = {"reviews", "dft_tools", "mlip", "solid_transport", "electrolytes", "interfaces", "electrode_screening", "electrochem_modeling"}
CATEGORIES = {"chinese_original", "team_english"}
REGIONS = {"中国内地", "中国香港", "中国澳门", "中国台湾"}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
REGISTRY_KEYS = {"schema_version", "as_of", "topics", "entries"}
ENTRY_KEYS = {"id", "category", "topic", "paper_id", "reference", "authors_basis", "language_evidence", "why_read", "practice", "caution", "collaboration_note"}


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def safe_url(value: object, *, required: bool = False) -> str:
    raw = str(value or "").strip()
    if not SAFE_URL.fullmatch(raw):
        if required:
            raise ValueError(f"unsafe source URL: {raw[:80]}")
        return "#"
    parsed = urlsplit(raw)
    if not parsed.hostname or parsed.username or parsed.password or any(k.lower() in {"sig", "signature", "token", "x-amz-signature", "expires"} for k in re.findall(r"(?:^|&)([^=]+)=", parsed.query)):
        raise ValueError("signed or credentialed source URL is not allowed")
    return raw


def _nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _title_records(title_records: object) -> dict:
    if title_records is None:
        return {}
    if isinstance(title_records, dict) and isinstance(title_records.get("papers"), dict):
        return title_records["papers"]
    if isinstance(title_records, dict):
        return title_records
    raise ValueError("title_records must be a mapping")


def validate(registry: dict, papers: list[dict], title_records: object = None) -> list[dict]:
    if not isinstance(registry, dict) or set(registry) != REGISTRY_KEYS or registry.get("schema_version") != 1:
        raise ValueError("domestic registry has an unsupported schema or fields")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(registry.get("as_of", ""))):
        raise ValueError("registry as_of must be YYYY-MM-DD")
    topics = registry.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("registry topics must be a nonempty list")
    topic_ids = []
    for topic in topics:
        if not isinstance(topic, dict) or set(topic) != {"id", "label"} or topic.get("id") not in TOPICS:
            raise ValueError("invalid topic record")
        _nonempty(topic.get("label"), "topic label")
        topic_ids.append(topic["id"])
    if len(topic_ids) != len(set(topic_ids)):
        raise ValueError("duplicate topic id")
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("registry entries must be a nonempty list")
    catalog = {str(p.get("id")): p for p in papers if isinstance(p, dict) and p.get("id")}
    titles = _title_records(title_records)
    seen_ids: set[str] = set(); seen_dois: set[str] = set(); categories: set[str] = set(); resolved = []
    for entry in entries:
        if not isinstance(entry, dict) or not set(entry).issubset(ENTRY_KEYS) or not {"id", "category", "topic", "authors_basis", "why_read", "practice", "caution"}.issubset(entry):
            raise ValueError("entry contains disallowed or missing fields")
        eid = _nonempty(entry.get("id"), "entry id")
        if eid in seen_ids:
            raise ValueError("duplicate entry id")
        seen_ids.add(eid)
        category = entry.get("category")
        if category not in CATEGORIES or entry.get("topic") not in topic_ids:
            raise ValueError("invalid entry category or topic")
        categories.add(category)
        has_pid = bool(entry.get("paper_id")); has_ref = entry.get("reference") is not None
        if has_pid == has_ref:
            raise ValueError("entry must have exactly one paper_id or reference")
        if has_pid:
            pid = str(entry["paper_id"])
            if pid not in catalog:
                raise ValueError(f"unknown canonical paper id: {pid}")
            source = catalog[pid]
            title_row = titles.get(pid)
            if not isinstance(title_row, dict) or not _nonempty(title_row.get("title"), "title map title") or title_row.get("title") != source.get("title") or title_row.get("doi") != source.get("doi"):
                raise ValueError(f"title map mismatch for {pid}")
        else:
            ref = entry["reference"]
            if not isinstance(ref, dict) or not set(ref).issubset({"title", "title_en", "authors", "year", "journal", "doi", "url", "volume", "issue", "pages", "document_type"}):
                raise ValueError("reference contains disallowed fields")
            _nonempty(ref.get("title"), "reference title")
            if not isinstance(ref.get("authors"), list) or not ref["authors"] or any(not isinstance(a, str) or not a.strip() for a in ref["authors"]):
                raise ValueError("reference authors must be a nonempty list")
            source = ref
        for field in ("title", "journal"):
            _nonempty(source.get(field), field)
        if type(source.get("year")) is not int or source["year"] < 1800 or source["year"] > 2200:
            raise ValueError("year must be a valid integer")
        if not isinstance(source.get("authors"), list) or not source["authors"] or any(not isinstance(a, str) or not a.strip() for a in source["authors"]):
            raise ValueError("authors must be nonempty strings")
        if source.get("url") is not None: safe_url(source.get("url"), required=True)
        doi = str(source.get("doi", "")).strip().lower()
        if not doi or not DOI_RE.fullmatch(doi): raise ValueError("each entry requires a valid DOI")
        if doi in seen_dois: raise ValueError("duplicate DOI")
        seen_dois.add(doi)
        basis = entry.get("authors_basis")
        if not isinstance(basis, list) or not basis:
            raise ValueError("authors_basis must be nonempty")
        for person in basis:
            if not isinstance(person, dict) or set(person) != {"name", "role", "institution", "region", "source_url", "locator"}:
                raise ValueError("authors_basis has disallowed fields")
            _nonempty(person.get("name"), "author name")
            if person.get("role") not in {"first", "corresponding"}:
                raise ValueError("author role must be first or corresponding")
            _nonempty(person.get("institution"), "institution")
            if person.get("region") not in REGIONS: raise ValueError("author region must be a supported domestic region")
            _nonempty(person.get("locator"), "evidence locator")
            safe_url(person.get("source_url"), required=True)
        if category == "chinese_original":
            language = entry.get("language_evidence")
            if not isinstance(language, dict) or set(language) != {"source_url", "locator", "note"}:
                raise ValueError("Chinese originals require language_evidence")
            safe_url(language.get("source_url"), required=True); _nonempty(language.get("locator"), "language locator"); _nonempty(language.get("note"), "language note")
        for key in ("why_read", "practice", "caution"):
            _nonempty(entry.get(key), key)
        if entry.get("collaboration_note") is not None: _nonempty(entry["collaboration_note"], "collaboration_note")
        resolved.append({"entry": entry, "source": source, "canonical": has_pid, "title_zh": (titles.get(str(entry.get("paper_id")), {}) or {}).get("title_zh", "")})
    if categories != CATEGORIES:
        raise ValueError("registry must contain both Chinese originals and team English papers")
    return resolved


def _link(url: object, label: str) -> str:
    return f'<a href="{esc(safe_url(url))}" target="_blank" rel="noreferrer noopener">{esc(label)}</a>'


def _route_info(row: dict, route: dict | None) -> dict:
    """Return display-only route metadata without duplicating catalog records."""
    if not route or row["entry"].get("category") != "chinese_original" or not row["canonical"]:
        return {}
    pid = str(row["entry"].get("paper_id", ""))
    mapping = route.get("papers", {}).get(pid, {}) if isinstance(route, dict) else {}
    if not isinstance(mapping, dict):
        return {}
    stages = {str(item.get("id")): item for item in route.get("stages", []) if isinstance(item, dict)}
    frontiers = {str(item.get("id")): item for item in route.get("frontiers", []) if isinstance(item, dict)}
    stage = str(mapping.get("stage", ""))
    stage_item = stages.get(stage, {})
    stage_label = "baseline" if stage == "baseline" else str(stage_item.get("label", stage)).split(" · ", 1)[0]
    frontier_rows = []
    for fid in mapping.get("frontiers", []):
        item = frontiers.get(str(fid))
        if item:
            frontier_rows.append({"id": str(fid), "label": str(item.get("label", fid))})
    return {"stage": stage, "stage_label": stage_label, "frontiers": frontier_rows}


def _validate_chinese_route(rows: list[dict], route: dict) -> None:
    """Fail closed when the authoritative route is present."""
    if not isinstance(route, dict) or not isinstance(route.get("papers"), dict):
        raise ValueError("route must contain a papers mapping")
    stages = {str(item.get("id")) for item in route.get("stages", []) if isinstance(item, dict)}
    frontiers = {str(item.get("id")) for item in route.get("frontiers", []) if isinstance(item, dict)}
    mappings = route["papers"]
    for row in rows:
        if row["entry"].get("category") != "chinese_original":
            continue
        if not row["canonical"]:
            raise ValueError("route-backed Chinese originals must reference canonical paper_id")
        pid = str(row["entry"].get("paper_id", ""))
        mapping = mappings.get(pid)
        if not isinstance(mapping, dict):
            raise ValueError(f"Chinese original has no route mapping: {pid}")
        if mapping.get("stage") not in stages:
            raise ValueError(f"Chinese original has unknown route stage: {pid}")
        unknown = [fid for fid in mapping.get("frontiers", []) if str(fid) not in frontiers]
        if unknown:
            raise ValueError(f"Chinese original has unknown frontier mapping: {pid}")


def _card(row: dict, route: dict | None = None) -> str:
    e, source = row["entry"], row["source"]
    title = source.get("title", "")
    title_en = source.get("title_en", "")
    subtitle = title_en or (row["title_zh"] if row["canonical"] else "")
    if subtitle.strip() == title.strip():
        subtitle = ""
    subtitle_lang = "en" if title_en else "zh-CN"
    authors = source.get("authors", [])
    if not isinstance(authors, list): authors = []
    doi = source.get("doi", "")
    doi_link = f'https://doi.org/{quote(str(doi).strip(), safe="./")}' if doi else source.get("url", "#")
    topic_label = row.get("topic_label", e.get("topic", ""))
    route_info = _route_info(row, route)
    route_terms = [route_info.get("stage_label", ""), *(f.get("label", "") for f in route_info.get("frontiers", []))]
    searchable = " ".join(str(x) for x in [title, subtitle, *authors, source.get("journal", ""), source.get("year", ""), source.get("doi", ""), topic_label, e.get("why_read", ""), *route_terms, *(p.get("name", "") for p in e["authors_basis"]), *(p.get("institution", "") for p in e["authors_basis"]), *(p.get("region", "") for p in e["authors_basis"])])
    citation = " · ".join(str(source.get(k)).strip() for k in ("volume", "issue", "pages", "document_type") if source.get(k))
    canonical_target = "./index.html?paper=" + quote(str(e.get("paper_id", "")), safe="")
    canonical_link = f' · <a href="{esc(canonical_target)}">主库记录</a>' if row["canonical"] else ""
    category_label = "中文原文" if e["category"] == "chinese_original" else "国内团队英文"
    role_label = {"first": "第一作者", "corresponding": "通讯作者"}
    basis_html = "<ul>" + "".join(f'<li>{esc(p["name"])}（{esc(role_label[p["role"]])}） · {esc(p["institution"])} · {esc(p["region"])} · {esc(p["locator"])} · {_link(p["source_url"], "证据")}</li>' for p in e["authors_basis"]) + "</ul>"
    lang = e.get("language_evidence")
    language_html = f'中文原文证据：{esc(lang["locator"])} · {esc(lang["note"])} · {_link(lang["source_url"], "查看语言证据")}' if lang else ""
    collaboration = f'<p>合作说明：{esc(e["collaboration_note"])}</p>' if e.get("collaboration_note") else ""
    card_id = "domestic-card-" + re.sub(r"[^A-Za-z0-9_-]+", "-", str(e.get("id", "entry")))
    route_badges = ""
    if route_info:
        stage_href = "./learning-route.html#stage-" + quote(route_info["stage"], safe="")
        route_badges = f'<span class="route-badge stage-badge"><a href="{esc(stage_href)}">{esc(route_info["stage_label"])}</a></span>'
        for frontier in route_info["frontiers"]:
            frontier_href = "./learning-route.html#frontier-" + quote(frontier["id"], safe="")
            route_badges += f'<span class="route-badge frontier-badge"><a href="{esc(frontier_href)}">{esc(frontier["label"])}</a></span>'
    return f'''<article class="domestic-card" id="{esc(card_id)}" data-entry-id="{esc(e.get("id", ""))}" data-category="{esc(e["category"])}" data-topic="{esc(e["topic"])}" data-stage="{esc(route_info.get("stage", ""))}" data-frontiers="{esc(" ".join(f["id"] for f in route_info.get("frontiers", [])))}" data-search="{esc(searchable)}">
      <h3>{esc(title)}</h3>{f'<p class="paper-subtitle" lang="{subtitle_lang}">{esc(subtitle)}</p>' if subtitle else ''}
      <p class="paper-meta">{esc(source.get("journal", ""))} · {esc(source.get("year", ""))} · {esc(category_label)} · 主题：{esc(topic_label)}{f' · {esc(citation)}' if citation else ''}</p>{f'<p class="route-badges" aria-label="学习路线">{route_badges}</p>' if route_badges else ''}
      <p class="paper-meta">{esc(doi or "无 DOI")}</p>
      <details><summary>阅读提示与单位依据</summary><p><strong>为什么读：</strong>{esc(e["why_read"])}</p><p><strong>小练习：</strong>{esc(e["practice"])}</p><p><strong>注意：</strong>{esc(e["caution"])}</p><div class="paper-evidence"><p>单位证据：</p>{basis_html}</div>{f'<p>{language_html}</p>' if language_html else ''}{collaboration}</details>
      <p class="paper-links">{_link(doi_link, "DOI / 出版商证据")}{f' · {_link(source.get("url"), "主要来源")}' if source.get("url") and source.get("url") != doi_link else ''}{canonical_link}</p>
    </article>'''


def _route_groups(rows: list[dict], route: dict | None, stage: str) -> str:
    selected = [row for row in rows if _route_info(row, route).get("stage") == stage]
    return "".join(_card(row, route) for row in selected)


def _frontier_crossrefs(rows: list[dict], route: dict | None) -> str:
    if not route:
        return ""
    frontier_rows = [item for item in route.get("frontiers", []) if isinstance(item, dict)]
    rendered = []
    for frontier in frontier_rows:
        fid = str(frontier.get("id", ""))
        links = []
        for row in rows:
            info = _route_info(row, route)
            if fid in {item["id"] for item in info.get("frontiers", [])}:
                target = "#domestic-card-" + re.sub(r"[^A-Za-z0-9_-]+", "-", str(row["entry"].get("id", "entry")))
                links.append(f'<a class="domestic-frontier-link" data-target-card="{esc(target[1:])}" href="{esc(target)}">{esc(row["source"].get("title", row["entry"].get("id", "")))}</a>')
        rendered.append(f'<details class="domestic-frontier-group" data-frontier="{esc(fid)}" data-search="{esc(str(frontier.get("label", "")))}"><summary>{esc(frontier.get("label", fid))} <small>{len(links)} 篇交叉引用</small></summary><div class="domestic-frontier-links">{" · ".join(links) if links else "暂无已映射中文条目"}</div></details>')
    return "".join(rendered)


def build(registry: dict, papers: list[dict], title_records: object, stylesheet_text: str = "", route: dict | None = None) -> str:
    rows = validate(registry, papers, title_records)
    if route is not None:
        _validate_chinese_route(rows, route)
    category_counts = {category: sum(row["entry"]["category"] == category for row in rows) for category in CATEGORIES}
    topics = {t["id"]: t["label"] for t in registry["topics"]}
    for row in rows: row["topic_label"] = topics[row["entry"]["topic"]]
    cards = {cat: "".join(_card(r, route) for r in rows if r["entry"]["category"] == cat) for cat in CATEGORIES}
    chinese_rows = [r for r in rows if r["entry"]["category"] == "chinese_original"]
    route_stages = [("baseline", "baseline"), ("beginner", "入门"), ("intermediate", "进阶"), ("frontier", "前沿")]
    if route:
        stage_defs = {str(s.get("id")): s for s in route.get("stages", []) if isinstance(s, dict)}
        route_stages = [(stage, "baseline" if stage == "baseline" else str(stage_defs.get(stage, {}).get("label", label)).split(" · ", 1)[0]) for stage, label in route_stages]
    route_sections = []
    for stage, label in route_stages:
        stage_cards = _route_groups(chinese_rows, route, stage) if route else ""
        if route and stage == "frontier":
            stage_cards += f'<div class="domestic-frontier-groups" aria-label="前沿方向">{_frontier_crossrefs(chinese_rows, route)}</div>'
        route_intro = ""
        if route:
            summary = stage_defs.get(stage, {}).get("summary", "")
            target = "./learning-route.html#stage-" + quote(stage, safe="")
            route_intro = f'<p class="stage-note">{esc(summary)} <a href="{esc(target)}">本阶段基础知识、验证与论文结构 →</a></p>'
        open_attr = " open" if stage == "baseline" else ""
        kicker = {"baseline": "常备", "beginner": "01", "intermediate": "02", "frontier": "03"}[stage]
        route_sections.append(f'<details class="domestic-stage" data-stage="{esc(stage)}" data-search="{esc(label)}"{open_attr}><summary><span class="stage-kicker">{esc(kicker)}</span><h3>{esc(label)}</h3><small>{stage_cards.count("class=\"domestic-card\"")} 篇唯一中文条目</small></summary><div class="domestic-stage-body">{route_intro}{stage_cards}</div></details>')
    chinese_content = "<div class=\"domestic-route-stages\">" + "".join(route_sections) + "</div>" if route else cards["chinese_original"]
    css = f"<style data-domestic-inline>{stylesheet_text}</style>" if stylesheet_text else ""
    options = ''.join(f'<option value="{esc(k)}">{esc(v)}</option>' for k,v in topics.items())
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>国内论文选读 · Battery Evidence Lab</title><link rel="stylesheet" href="./lab-ui.css"><link rel="stylesheet" href="./domestic-papers.css">{css}</head><body><main class="shell">
      <nav class="site-nav" aria-label="站点导航"><a class="brand" href="./index.html#top">Battery Evidence Lab</a><div class="site-nav-links"><a href="./index.html#research-question">证据问答</a><a href="./foundations.html">基础地图</a><a href="./future-directions.html">未来方向</a><a href="./ai-battery-applications.html">AI 应用</a><a href="./learning-route.html">学习路线</a><a class="current" href="./domestic-papers.html" aria-current="page">国内论文</a></div></nav>
      <header><p class="eyebrow">专题选读</p><h1>国内论文选读</h1><p class="lede">中文原文与国内团队英文论文分开浏览；团队归属按发表时第一作者或通讯作者单位整理。</p><p class="collection-counts">{category_counts["chinese_original"]} 篇中文原文 · {category_counts["team_english"]} 篇国内团队英文 · 整理于 {esc(registry["as_of"])}</p><p class="notice">中文条目沿用主库的阶段分类。点阶段名查看基础知识、验证方法与论文结构，点题名查看论文和单位依据。</p><p class="project-progress" data-project-progress>项目进度加载中…</p></header>
      <section class="controls" aria-label="筛选"><label>搜索 <input id="domestic-search" type="search" placeholder="标题、期刊、团队、主题"></label><label>类别 <select id="domestic-category"><option value="all">全部</option><option value="chinese_original">中文原文</option><option value="team_english">国内团队英文</option></select></label><label>主题 <select id="domestic-topic"><option value="all">全部</option>{options}</select></label><button id="domestic-reset" type="button">重置</button><span id="domestic-count" aria-live="polite"></span></section>
      <section class="domestic-group" data-group="chinese_original"><h2>中文期刊 / 中文原文 <small>{category_counts["chinese_original"]} 篇</small></h2><div class="domestic-grid">{chinese_content}</div></section><section class="domestic-group" data-group="team_english"><h2>国内团队英文论文 <small>{category_counts["team_english"]} 篇</small></h2><div class="domestic-grid">{cards["team_english"]}</div></section><p id="domestic-empty" class="no-results" hidden>没有匹配的论文。</p>
      <script defer src="./lab-ui.js"></script><script defer src="./domestic-papers.js"></script></main></body></html>'''


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")); papers = json.loads(PAPERS_PATH.read_text(encoding="utf-8")); titles = json.loads(TITLE_PATH.read_text(encoding="utf-8")); route = json.loads((ROOT / "data" / "learning_route.json").read_text(encoding="utf-8"))
    css = (ROOT / "static" / "domestic-papers.css").read_text(encoding="utf-8")
    rendered = build(registry, papers, titles, css, route=route)
    OUT_PATH.write_text(rendered, encoding="utf-8")


if __name__ == "__main__": main()
