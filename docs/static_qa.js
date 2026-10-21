/* Pure, fail-closed lookup for the curated metadata extension. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.BatteryStaticQA = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';
  const NOTICE = '关键词/字符匹配与元数据导读，非模型生成；具体参数需核对原文';
  const intents = {
    limits: ['限制', '局限', '范围', '核对', 'limit', 'scope', 'caveat', 'verify'],
    methods: ['方法', '工具', '怎么做', '软件', 'method', 'software', 'workflow', 'protocol'],
    reading: ['阅读', '路线', '先读', '入门', '阶段', 'read', 'route', 'baseline', 'beginner']
  };
  const questions = { overview: '这篇论文在目录中的定位和主题是什么？', methods: '目录记录了哪些方法或工具？', limitations: '从公开元数据看，这篇论文有哪些范围限制或需要核对之处？', reading: '这篇论文在学习路线中应如何阅读，为什么？' };
  const validUrl = u => typeof u === 'string' && /^https:\/\/doi\.org\/10\.\d{4,9}\/[\-._;()/:A-Z0-9]+$/i.test(u);
  const text = v => typeof v === 'string' ? v.toLocaleLowerCase() : '';
  const exactKeys = (v, keys) => v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === keys.length && keys.every(k => Object.prototype.hasOwnProperty.call(v, k));
  const tokens = q => text(q).match(/[\p{L}\p{N}]+/gu) || [];
  function inferIntent(q) {
    const s = text(q);
    for (const k of ['limits', 'methods', 'reading']) if (intents[k].some(x => s.includes(x))) return k === 'limits' ? 'limitations' : k;
    return 'overview';
  }
  function validDataset(d) {
    if (!exactKeys(d, ['schema_version','as_of','catalog_count','qa_count','catalog_fingerprint','static_extension','evidence_level','entries']) || !/^\d{4}-\d{2}-\d{2}$/.test(d.as_of || '') || !/^[a-f0-9]{64}$/.test(d.catalog_fingerprint || '') || d.schema_version !== 1 || d.static_extension !== true || d.evidence_level !== 'curated_metadata' || !Number.isSafeInteger(d.catalog_count) || d.catalog_count < 1 || d.qa_count !== d.catalog_count * 4 || !Array.isArray(d.entries) || d.entries.length !== d.catalog_count) return false;
    const ids = new Set(), dois = new Set();
    for (const e of d.entries) {
      if (!exactKeys(e, ['paper_id','doi','title','title_zh','qa_ids','qas']) || typeof e.paper_id !== 'string' || !e.paper_id.trim() || ids.has(e.paper_id) || typeof e.doi !== 'string' || !validUrl('https://doi.org/' + e.doi) || dois.has(e.doi.toLowerCase()) || typeof e.title !== 'string' || !e.title.trim() || typeof e.title_zh !== 'string' || !Array.isArray(e.qas) || e.qas.length !== 4 || !Array.isArray(e.qa_ids) || e.qa_ids.length !== 4 || new Set(e.qa_ids).size !== 4) return false;
      ids.add(e.paper_id);
      dois.add(e.doi.toLowerCase());
      const intentsSeen = new Set();
      for (const qa of e.qas) {
        const expectedFields = { overview: ['role','summary'], methods: ['methods'], limitations: ['scope_note'], reading: ['learning_route.stage','learning_route.rationale'] };
        if (!qa || Object.keys(qa).length !== 6 || !['overview','methods','limitations','reading'].includes(qa.intent) || intentsSeen.has(qa.intent) || qa.id !== e.paper_id + ':' + qa.intent || !e.qa_ids.includes(qa.id) || qa.question !== questions[qa.intent] || typeof qa.answer !== 'string' || !Array.isArray(qa.source_fields) || JSON.stringify(qa.source_fields) !== JSON.stringify(expectedFields[qa.intent]) || !Array.isArray(qa.source_urls) || qa.source_urls.length !== 1 || !validUrl(qa.source_urls[0]) || qa.source_urls[0].toLowerCase() !== ('https://doi.org/' + e.doi).toLowerCase()) return false;
        intentsSeen.add(qa.intent);
      }
      if (intentsSeen.size !== 4) return false;
    }
    return ids.size === d.catalog_count;
  }
  function lookup(question, matchedPapers, dataset, options) {
    const empty = { kind: 'static_metadata_extension', label: '静态知识延伸', notice: NOTICE, cards: [], coverage: { papers: 0, qa: 0 } };
    if (typeof question !== 'string' || !question.trim() || !Array.isArray(matchedPapers) || !validDataset(dataset)) return empty;
    const limit = Math.max(0, Math.min(3, Number.isFinite(options && options.limit) ? Math.floor(options.limit) : 3));
    if (!limit) return Object.assign(empty, { intent: inferIntent(question) });
    const byId = new Map();
    for (const p of matchedPapers) {
      if (!p || typeof p !== 'object' || typeof p.id !== 'string' || typeof p.doi !== 'string' || typeof p.title !== 'string') continue;
      if (byId.has(p.id)) continue;
      const e = dataset.entries.find(x => x.paper_id === p.id && x.doi.toLowerCase() === p.doi.toLowerCase() && x.title === p.title);
      if (e) byId.set(p.id, e);
    }
    const intent = inferIntent(question), queryTokens = tokens(question);
    const scored = [];
    for (const e of byId.values()) {
      const qa = e.qas.find(q => q.intent === intent) || e.qas.find(q => q.intent === 'overview');
      const hay = text([e.title, e.title_zh, qa.question, qa.answer, qa.intent].join(' '));
      const score = queryTokens.reduce((n, t) => n + (hay.includes(t) ? 1 : 0), 0) + (qa.intent === intent ? 1 : 0);
      if (score > 0) scored.push({ e, qa, score });
    }
    const seen = new Set(), cards = [];
    for (const item of scored) {
      if (seen.has(item.e.paper_id) || cards.length >= limit) continue;
      seen.add(item.e.paper_id);
      const related = item.e.qas.filter(q => q.id !== item.qa.id).slice(0, 3);
      cards.push({ paper_id: item.e.paper_id, doi: item.e.doi, title: item.e.title, title_zh: item.e.title_zh || '', primary: item.qa, related, evidence_level: 'curated_metadata' });
    }
    return { kind: 'static_metadata_extension', label: '静态知识延伸', notice: NOTICE, cards, coverage: { papers: dataset.catalog_count, qa: dataset.qa_count }, intent };
  }
  return { lookup };
});
