(() => {
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  let map = {};
  const ready = fetch('./data/paper_titles_zh.json', { cache: 'no-store' })
    .then(response => response.ok ? response.json() : {})
    .then(payload => { map = payload && payload.papers && typeof payload.papers === 'object' ? payload.papers : {}; return map; })
    .catch(() => map);
  const progressReady = fetch('./data/project_status.json', { cache: 'no-store' })
    .then(response => response.ok ? response.json() : {})
    .then(status => {
      const values = status && typeof status === 'object' ? status : {};
      const asOf = values.as_of;
      const papers = values.papers;
      const rows = values.dataset_rows;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(asOf || '') || !Number.isSafeInteger(papers) || papers < 0 || !Number.isSafeInteger(rows) || rows < 0) return {};
      const staticQa = values.static_qa;
      const staticCount = staticQa && staticQa.catalog_papers === papers && Number.isSafeInteger(staticQa.rows) && staticQa.rows === papers * 4 ? staticQa.rows : null;
      const knowledgeCount = Number.isSafeInteger(values.research_knowledge?.cards) && values.research_knowledge.cards > 0 ? values.research_knowledge.cards : null;
      const paint = () => document.querySelectorAll('[data-project-progress]').forEach(node => {
        node.textContent = `${papers} 篇论文 · 更新于 ${asOf}`;
      });
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paint, { once: true });
      else paint();
      return values;
    }).catch(() => ({}));
  const titleZh = (paperOrId, englishTitle) => {
    const id = typeof paperOrId === 'object' ? paperOrId?.id : paperOrId;
    const paper = typeof paperOrId === 'object' ? paperOrId : null;
    const row = Object.prototype.hasOwnProperty.call(map, id) ? map[id] : {};
    const canonical = paper?.title || englishTitle;
    if (canonical && row.title !== canonical) return '';
    return typeof row.title_zh === 'string' ? row.title_zh : '';
  };
  const paperTitleHtml = (paperOrId, englishTitle) => {
    const paper = paperOrId && typeof paperOrId === 'object' ? paperOrId : { id: paperOrId, title: englishTitle };
    const english = paper.title || englishTitle || '';
    const zh = titleZh(paper);
    return `<span class="paper-title-en">${escapeHtml(english)}</span>${zh && zh.trim() !== english.trim() ? `<span class="paper-title-zh" lang="zh-CN">${escapeHtml(zh)}</span>` : ''}`;
  };
  const metadata = (paperOrId) => {
    const id = typeof paperOrId === 'object' ? paperOrId?.id : paperOrId;
    return map[id] || {};
  };
  const verificationLabel = value => {
    const flag = String(value || '');
    if (flag === 'verified') return '书目已核验';
    if (flag.startsWith('verified_crossref')) return flag.includes('publisher') ? 'Crossref 与出版社已核验' : 'Crossref 已核验';
    if (flag === 'verified_wos_record') return 'WOS 记录已核验';
    if (/^verified_(publisher|nature|frontiers|acs_repository|rsc_|pubmed_publisher|primary_fulltext)/.test(flag)) return flag.includes('pdf') || flag.includes('fulltext') ? '出版社与正文已核验' : '出版社书目已核验';
    return '书目核验状态待补充';
  };
  const paperSummary = paper => {
    const role = String(paper?.role || '').trim().replace(/[。；;]+$/, '');
    const summary = String(paper?.summary || '').trim();
    const usefulRole = /面向电池电解液、固态电解质、正极\/界面模拟的可复用计算文献/.test(role) ? '' : role;
    const usefulSummary = /^基于\s*(?:Crossref\s*)?出版社元数据核验[:：]/i.test(summary) ? '' : summary;
    const comparable = value => value.normalize('NFKC').replace(/\s+/g, ' ').replace(/[。.!！；;]+$/, '').trim();
    if (usefulRole && usefulSummary && comparable(usefulRole) === comparable(usefulSummary)) return usefulSummary;
    return [usefulRole, usefulSummary].filter(Boolean).join(' · ') || '内容摘录待补充';
  };
  window.LabUI = { ready, progressReady, escapeHtml, titleZh, paperTitleHtml, metadata, verificationLabel, paperSummary, get titles() { return map; } };
  window.labUIReady = ready;
})();
