/* Pure, fail-closed retrieval for curated research knowledge cards. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.BatteryResearchKnowledge = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';
  const NOTICE = '文献与官方文档整理，非实时模型生成；具体参数需按体系验证';
  const kinds = new Set(['foundation', 'workflow', 'faq']);
  const docHosts = new Set(['vasp.at', 'www.vasp.at/wiki', 'vaspkit.com', 'docs.lammps.org', 'ase-lib.org', 'docs.ase-lib.org', 'pymatgen.org', 'docs.deepmodeling.com', 'docs.materialsproject.org']);
  const cardKeys = ['id','kind','question','aliases','all_of','answer','steps','checks','boundary','sources','documentation','tags'];
  const sourceKeys = ['paper_id','doi','locator','note'];
  const docKeys = ['label','url','locator'];
  const exact = (x, keys) => x && typeof x === 'object' && !Array.isArray(x) && Object.keys(x).length === keys.length && keys.every(k => Object.prototype.hasOwnProperty.call(x, k));
  const txt = x => typeof x === 'string' && !!x.trim() && x.length <= 4000;
  const norm = x => typeof x === 'string' ? x.normalize('NFKC').trim().toLocaleLowerCase() : '';
  const triggerHit = (q, trigger) => {
    const t = norm(trigger); if (!t) return false;
    if (/^[\x00-\x7f]+$/.test(t)) return new RegExp('(^|[^a-z0-9])' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z0-9]|$)', 'i').test(q);
    return q.includes(t);
  };
  function valid(data, papers) {
    if (!exact(data, ['schema_version','as_of','cards']) || data.schema_version !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(data.as_of) || !Array.isArray(data.cards) || !data.cards.length || !Array.isArray(papers)) return false;
    const canonical = new Map(), dois = new Set();
    for (const p of papers) {
      if (!p || typeof p.id !== 'string' || !p.id.trim() || typeof p.doi !== 'string' || !p.doi.trim() || canonical.has(p.id) || dois.has(p.doi)) return false;
      canonical.set(p.id, p.doi); dois.add(p.doi);
    }
    const ids = new Set();
    for (const c of data.cards) {
      if (!exact(c, cardKeys) || !txt(c.id) || ids.has(c.id) || !kinds.has(c.kind) || !txt(c.question) || !Array.isArray(c.aliases) || c.aliases.length < 2 || c.aliases.length > 4 || c.aliases.some(x => !txt(x)) || !Array.isArray(c.all_of) || !c.all_of.length || c.all_of.some(g => !Array.isArray(g) || !g.length || g.some(x => !txt(x))) || !txt(c.answer) || !txt(c.boundary) || !['steps','checks'].every(k => Array.isArray(c[k]) && c[k].length >= 1 && c[k].length <= 20 && c[k].every(txt)) || !Array.isArray(c.tags) || !c.tags.length || c.tags.some(x => !txt(x))) return false;
      ids.add(c.id);
      if (!Array.isArray(c.sources) || !c.sources.length || c.sources.some(s => !exact(s, sourceKeys) || !txt(s.paper_id) || !txt(s.doi) || canonical.get(s.paper_id) !== s.doi || !txt(s.locator) || !txt(s.note))) return false;
      if (!Array.isArray(c.documentation) || c.documentation.some(d => { if (!exact(d, docKeys) || !txt(d.label) || !txt(d.locator) || !txt(d.url)) return true; try { const u = new URL(d.url), hp = (u.host + u.pathname).replace(/\/$/, '').toLowerCase(); return u.protocol !== 'https:' || !Array.from(docHosts).some(h => hp === h || hp.startsWith(h + '/')) || u.username || u.password; } catch (_) { return true; } })) return false;
    }
    return true;
  }
  function lookup(question, catalog, dataset, options) {
    const empty = { kind: 'curated_research_knowledge', label: '基础知识与计算问答', notice: NOTICE, cards: [], coverage: { cards: 0 } };
    if (!valid(dataset, catalog) || typeof question !== 'string' || !question.trim()) return empty;
    const q = norm(question), limit = Math.max(0, Math.min(3, Number.isFinite(options && options.limit) ? Math.floor(options.limit) : 3));
    if (!limit) return empty;
    const ranked = dataset.cards.map((c, index) => {
      const exactMatch = norm(c.question) === q || c.aliases.some(a => norm(a) === q);
      const groups = c.all_of.reduce((n, g) => n + (g.some(t => triggerHit(q, t)) ? 1 : 0), 0);
      if (!exactMatch && groups !== c.all_of.length) return null;
      return { c, index, exact: exactMatch ? 1 : 0, groups };
    }).filter(Boolean).sort((a, b) => b.exact - a.exact || b.groups - a.groups || (a.c.kind === 'faq' ? -1 : 0) - (b.c.kind === 'faq' ? -1 : 0) || a.index - b.index).slice(0, limit);
    const title = new Map(catalog.map(p => [p.id, p.title]));
    return { kind: empty.kind, label: empty.label, notice: empty.notice, cards: ranked.map(({c}) => ({...c, sources: c.sources.map(s => ({...s, title: title.get(s.paper_id) || ''}))})), coverage: { cards: dataset.cards.length } };
  }
  return { lookup };
});
