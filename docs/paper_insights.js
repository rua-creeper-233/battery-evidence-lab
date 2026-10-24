(function (root) {
  'use strict';
  const SECTION_LABELS = {
    research_question: '研究问题', systems: '系统与对象', methods: '方法',
    findings: '主要发现', limits: '局限与边界', reproduction: '复现提示'
  };
  const SECTION_ORDER = Object.keys(SECTION_LABELS);
  let payload = null;
  const text = v => String(v == null ? '' : v).trim();
  const esc = v => text(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const privateHost = host => {
    const h = String(host || '').toLowerCase().replace(/^\[|\]$/g, '');
    if (h === 'localhost' || h === '::1' || h === '0.0.0.0' || h.endsWith('.local')) return true;
    const nums = h.split('.').map(Number);
    if (nums.length === 4 && nums.every(Number.isInteger) && nums.every(n => n >= 0 && n <= 255)) return nums[0] === 10 || nums[0] === 127 || (nums[0] === 192 && nums[1] === 168) || (nums[0] === 172 && nums[1] >= 16 && nums[1] <= 31);
    return false;
  };
  const safeUrl = value => { try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password && !privateHost(u.hostname) ? u.href : ''; } catch (_) { return ''; } };
  const validRef = (item, sourceIds) => Array.isArray(item.source_refs) && item.source_refs.length > 0 && item.source_refs.every(id => sourceIds.has(id));
  const validDate = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(value + 'T00:00:00Z');
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  };
  function normalize(input, catalog) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
    if (input.schema_version !== 1 || !input.papers || typeof input.papers !== 'object' || Array.isArray(input.papers)) return null;
    if (!validDate(input.as_of) || !input.methodology || typeof input.methodology !== 'object' || Array.isArray(input.methodology) || Object.keys(input.methodology).some(k => !['reference_title','reference_url','implemented_layers','note'].includes(k)) || !['reference_title','reference_url','implemented_layers','note'].every(k => typeof input.methodology[k] === 'string' && text(input.methodology[k])) || !safeUrl(input.methodology.reference_url)) return null;
    const catalogMap = Array.isArray(catalog) ? new Map(catalog.filter(p => p && typeof p.id === 'string').map(p => [p.id, p])) : null;
    const out = {schema_version: 1, as_of: text(input.as_of), methodology: {...input.methodology}, papers: {}};
    for (const [key, raw] of Object.entries(input.papers)) {
      if (!raw || typeof raw !== 'object' || Array.isArray(raw) || text(raw.paper_id) !== key) continue;
      if (catalogMap && !catalogMap.has(key)) continue;
      if (catalogMap && raw.doi && text(catalogMap.get(key).doi).toLowerCase() !== text(raw.doi).toLowerCase()) continue;
      if (!Array.isArray(raw.sources) || !raw.sources.length) continue;
      const sources = raw.sources.map(s => s && typeof s === 'object' && !Array.isArray(s) ? ({id:text(s.id), url:safeUrl(s.url), scope:text(s.scope), locator:text(s.locator)}) : null);
      if (sources.some(s => !s || !s.id || !s.url || !s.locator || !['abstract','article','author_code','catalog'].includes(s.scope)) || new Set(sources.map(s => s.id)).size !== sources.length) continue;
      const sourceIds = new Set(sources.map(s => s.id));
      const sections = {};
      let invalidRecord = false;
      for (const name of SECTION_ORDER) {
        const values = Array.isArray(raw.sections && raw.sections[name]) ? raw.sections[name].map(x => {
          if (!x || typeof x !== 'object' || Array.isArray(x) || !['reported','reading_guide'].includes(x.kind)) { invalidRecord = true; return null; }
          return {text:text(x.text), source_refs:Array.isArray(x.source_refs) ? x.source_refs.filter(id => typeof id === 'string').map(text) : [], kind:x.kind};
        }).filter(x => x && x.text && !/^(暂无|待补充|未知|n\/a|tbd)[。.!！]?$/i.test(x.text) && validRef(x, sourceIds)) : [];
        if (values.length) sections[name] = values;
      }
      const relations = Array.isArray(raw.relations) ? raw.relations.map(r => {
        if (!r || typeof r !== 'object' || Array.isArray(r) || !['reported','reading_guide'].includes(r.kind)) { invalidRecord = true; return null; }
        return {subject:text(r.subject), predicate:text(r.predicate), object:text(r.object), source_refs:Array.isArray(r.source_refs) ? r.source_refs.filter(id => typeof id === 'string').map(text) : [], kind:r.kind};
      }).filter(r => r && r.subject && r.predicate && r.object && validRef(r, sourceIds)) : [];
      if (invalidRecord) continue;
      out.papers[key] = {paper_id:key, doi:text(raw.doi), sources, sections, relations};
    }
    return Object.keys(input.papers).length && !Object.keys(out.papers).length ? null : out;
  }
  function recordFor(id) { return payload && payload.papers ? payload.papers[id] || null : null; }
  function sourceHint(item, record) {
    const refs = (item.source_refs || []).map(id => (record.sources || []).find(s => s.id === id)).filter(Boolean);
    if (!refs.length) return '';
    const labels = {abstract:'摘要',article:'正文',author_code:'作者代码',catalog:'题录'};
    return `<small class="paper-insight-source">来源：${refs.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${labels[s.scope] || esc(s.scope)}${s.locator ? ` · ${esc(s.locator)}` : ''}</a>`).join('；')}</small>`;
  }
  function itemHtml(item, record) {
    const guide = item.kind === 'reading_guide';
    return `<li class="paper-insight-item"><span>${esc(item.text)}</span>${guide ? '<em class="paper-insight-kind">阅读建议</em>' : ''}${sourceHint(item, record)}</li>`;
  }
  function renderHtml(id) {
    const record = recordFor(id); if (!record) return '';
    let html = '<section class="paper-insights" aria-labelledby="paper-insights-title"><h3 id="paper-insights-title">论文详情要点</h3>';
    let count = 0;
    for (const name of SECTION_ORDER) {
      const items = record.sections[name] || []; if (!items.length) continue;
      count += items.length; html += `<h4>${SECTION_LABELS[name]}</h4><ul>${items.map(i => itemHtml(i, record)).join('')}</ul>`;
    }
    if (record.relations.length) {
      count += record.relations.length; html += '<h4>实体—关系</h4><ul class="paper-insight-relations">' + record.relations.map(r => `<li><span>${esc(r.subject)} —[${esc(r.predicate)}]→ ${esc(r.object)}</span>${r.kind === 'reading_guide' ? '<em class="paper-insight-kind">阅读建议</em>' : ''}${sourceHint(r, record)}</li>`).join('') + '</ul>';
    }
    return count ? `${html}</section>` : '';
  }
  async function load(url='./data/paper_insights.json', catalog) {
    try { const response = await fetch(url, {cache:'no-store'}); if (!response.ok) throw new Error('unavailable'); const next = normalize(await response.json(), catalog); if (!next) throw new Error('invalid'); payload = next; return next; }
    catch (_) { payload = null; return null; }
  }
  root.PaperInsights = { normalize, renderHtml, render: renderHtml, recordFor, load, setData: (value, catalog) => { payload = normalize(value, catalog); return payload; }, get data() { return payload; } };
})(window);
