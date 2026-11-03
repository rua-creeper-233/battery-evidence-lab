/* Shared citation actions for dynamically rendered paper cards. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CitationTools = factory(root);
})(typeof globalThis !== 'undefined' ? globalThis : this, function (host) {
  'use strict';
  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const text = value => String(value == null ? '' : value).trim();
  const doiText = paper => text(paper && paper.doi).replace(/^https?:\/\/doi\.org\//i, '').replace(/^doi:\s*/i, '').trim();
  const authors = paper => Array.isArray(paper && paper.authors) ? paper.authors.map(text).filter(Boolean) : text(paper && paper.authors).split(/\s*;\s*/).filter(Boolean);
  const bibtex = paper => {
    if (!paper || typeof paper !== 'object' || !text(paper.title)) return '';
    const names = authors(paper), year = text(paper.year), journal = text(paper.journal), doi = doiText(paper);
    const first = (names[0] || 'paper').toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 24) || 'paper';
    const key = `${first}${year || ''}${text(paper.id).replace(/[^a-z0-9]+/gi, '').slice(0, 16)}` || 'paper';
    const texEscape = value => String(value).replace(/[\\&%$#_{}~^]/g, ch => ({'\\':'\\textbackslash{}', '~':'\\textasciitilde{}', '^':'\\textasciicircum{}'}[ch] || `\\${ch}`));
    const fields = [`  title = {{${texEscape(text(paper.title))}}}`];
    if (names.length) fields.push(`  author = {${texEscape(names.join(' and '))}}`);
    if (year) fields.push(`  year = {${texEscape(year)}}`);
    if (journal) fields.push(`  journal = {${texEscape(journal)}}`);
    if (doi) fields.push(`  doi = {${texEscape(doi)}}`);
    return `@article{${key},\n${fields.join(',\n')}\n}`;
  };
  const actionsHtml = paper => { const id = escapeHtml(paper && paper.id); const doi = doiText(paper); return `<span class="citation-actions" data-citation-actions>${doi ? `<button type="button" class="citation-button" data-citation-action="doi" data-paper-id="${id}">复制 DOI</button>` : ''}<button type="button" class="citation-button" data-citation-action="bibtex" data-paper-id="${id}">复制 BibTeX</button></span>`; };
  const copyFallback = value => { const area = document.createElement('textarea'); area.value = value; area.setAttribute('readonly', ''); area.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0'; document.body.appendChild(area); area.select(); let ok = false; try { ok = Boolean(document.execCommand && document.execCommand('copy')); } catch (_) {} area.remove(); return ok; };
  const copy = value => { if (!value) return Promise.reject(new Error('empty citation')); if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) return navigator.clipboard.writeText(value).catch(() => { if (!copyFallback(value)) throw new Error('clipboard unavailable'); }); return copyFallback(value) ? Promise.resolve() : Promise.reject(new Error('clipboard unavailable')); };
  const normalizeCatalog = payload => {
    if (Array.isArray(payload)) return payload.filter(row => row && typeof row === 'object' && row.id);
    if (payload && Array.isArray(payload.papers)) return payload.papers.filter(row => row && typeof row === 'object' && row.id);
    return [];
  };
  const createCatalogLoader = (options = {}) => {
    const stateHost = options.host || host;
    const fetchImpl = options.fetchImpl || (typeof fetch === 'function' ? fetch : null);
    let inflight = null, cached = [];
    const liveRows = () => normalizeCatalog(stateHost?.state?.papers);
    const load = () => {
      const live = liveRows();
      if (live.length) return Promise.resolve(live);
      if (cached.length) return Promise.resolve(cached);
      if (inflight) return inflight;
      if (!fetchImpl) return Promise.resolve([]);
      const urls = [options.catalogUrl || './data/papers.json', options.apiUrl || '/api/papers'];
      inflight = (async () => {
        for (const url of urls) {
          try {
            const response = await fetchImpl(url, { cache: 'no-store' });
            if (!response || !response.ok) continue;
            const rows = normalizeCatalog(await response.json());
            if (rows.length) return rows;
          } catch (_) {}
        }
        return [];
      })().then(rows => {
        const current = liveRows();
        cached = current.length ? current : rows;
        return cached;
      }).finally(() => { inflight = null; });
      return inflight;
    };
    return load;
  };
  const install = (options = {}) => {
    if (typeof document === 'undefined' || document.documentElement.dataset.citationToolsInstalled) return;
    document.documentElement.dataset.citationToolsInstalled = 'true';
    const catalog = createCatalogLoader(options);
    let statusTimer;
    const status = message => { let node = document.querySelector('[data-citation-status]'); if (!node) { node = document.createElement('div'); node.className = 'citation-status'; node.dataset.citationStatus = ''; node.setAttribute('role','status'); node.setAttribute('aria-live','polite'); document.body.appendChild(node); } clearTimeout(statusTimer); node.textContent = ''; setTimeout(() => { node.textContent = message; }, 0); statusTimer = setTimeout(() => { node.textContent = ''; }, 5000); };
    let lastTrigger = null;
    const manual = value => { let panel = document.querySelector('[data-citation-manual]'); if (!panel) { panel = document.createElement('div'); panel.dataset.citationManual = ''; panel.setAttribute('role','dialog'); panel.setAttribute('aria-label','手动复制引用'); panel.innerHTML = '<div><strong>请手动复制引用</strong><button type="button" data-citation-close aria-label="关闭">关闭</button></div><textarea readonly></textarea>'; document.body.appendChild(panel); const close = () => { panel.hidden = true; lastTrigger?.focus?.(); }; panel.querySelector('[data-citation-close]').addEventListener('click', close); panel.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); close(); } }); } panel.hidden = false; const area = panel.querySelector('textarea'); area.value = value; area.focus(); area.select(); };
    document.addEventListener('click', event => { const button = event.target.closest?.('[data-citation-action]'); if (!button) return; event.preventDefault(); event.stopPropagation(); lastTrigger = button; catalog().then(rows => { const paper = (Array.isArray(rows) ? rows : []).find(p => String(p?.id) === String(button.dataset.paperId)); const value = button.dataset.citationAction === 'doi' ? doiText(paper) : bibtex(paper); if (!value) { status('该论文缺少可用的引用信息。'); return; } return copy(value).then(() => status(button.dataset.citationAction === 'doi' ? 'DOI 已复制。' : 'BibTeX 已复制。')).catch(() => { status('无法写入剪贴板，请使用下方文本框手动复制。'); manual(value); }); }).catch(() => status('暂时无法加载论文引用信息。')); }, true);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => install(options), {once: true});
  };
  const api = { escapeHtml, doiText, bibtex, actionsHtml, copy, install, createCatalogLoader };
  if (typeof document !== 'undefined') install();
  return api;
});
