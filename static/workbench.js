(function() {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const e = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const list = value => Array.isArray(value) ? value : value ? [value] : [];
  const joined = value => list(value).filter(Boolean).join('、');
  const componentLabels = {cathode:'正极',anode:'负极',electrolyte:'电解质',separator:'隔膜',interface:'界面',collectors:'集流体'};
  const facetDefs = [
    ['component','组件','components'], ['region','团队地区','regions'], ['method','方法','methods'],
    ['software','软件','software'], ['type','论文类型','types'], ['year','年份','years'], ['evidence','证据覆盖','evidence'],
  ];
  const routeKeys = ['q', ...facetDefs.map(([key]) => key), 'sort'];
  const sourceFiles = {
    tags:'paper_tags', titles:'paper_titles_zh', components:'battery_components', domestic:'domestic_papers',
    insights:'paper_insights', searchConfig:'search_config', route:'learning_route',
  };
  const drawer = $('#evidence-dialog');
  const matrix = $('#compare-dialog');
  const status = $('#library-status');
  const results = $('#results');
  let model, sources, local;
  let route = {}, rows = [], page = 1, paperId = null, compare = [], previousFocus = null;

  async function json(url) {
    const res = await fetch(url, {signal: AbortSignal.timeout(4500)});
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }
  const optional = url => json(url).catch(() => null);

  async function localData() {
    if (!/^(localhost|127\.0\.0\.1|\[::1\])$/i.test(location.hostname)) return null;
    const health = await optional('/api/health');
    if (health?.ok !== true || health.service !== 'Battery Evidence Lab local API') return null;
    const [catalogue, zotero, literature, methods, tags] = await Promise.all([
      '/api/papers', '/api/zotero-links', '/api/literature', '/api/methods', '/api/paper-tags',
    ].map(optional));
    return {papers:catalogue?.papers, zotero:zotero?.items, literature:literature?.papers, methods:methods?.papers, tags};
  }

  async function start() {
    try {
      const requests = Object.entries(sourceFiles).map(async ([key, file]) => [key, await optional(`./data/${file}.json`)]);
      const [catalogue, metadata, connection] = await Promise.all([
        optional('./data/papers.json'), Promise.all(requests), localData(),
      ]);
      local = connection;
      const papers = Array.isArray(local?.papers) ? local.papers : catalogue;
      if (!Array.isArray(papers) || !papers.length) throw new Error('Catalogue unavailable');
      sources = Object.fromEntries(metadata);
      model = window.WorkbenchModel.create({
        ...sources, papers, tags:local?.tags || sources.tags, searchAgent:window.BatteryBrowserAgent,
      });
      status.textContent = `${local ? '本地服务已连接' : '静态证据库'} · ${model.papers.length} 篇`;
      $('#result-note').textContent = local ? '已接通本地文库' : '';
      results.setAttribute('aria-busy', 'false');
      renderFacets();
      restore();
    } catch (error) {
      results.replaceChildren();
      results.setAttribute('aria-busy', 'false');
      status.textContent = '证据库加载失败，请刷新页面。';
      $('#result-count').textContent = '加载失败';
      console.error('无法初始化论文工作台', error);
    }
  }

  function urlFor(id = paperId) {
    const params = new URLSearchParams();
    for (const key of routeKeys) if (route[key]) params.set(key, route[key]);
    if (id) params.set('paper', id);
    if (compare.length) params.set('compare', compare.join(','));
    const query = params.toString();
    return location.pathname + (query ? `?${query}` : '');
  }
  function write(push = false) {
    const url = urlFor();
    if (location.pathname + location.search === url) return;
    history[push ? 'pushState' : 'replaceState']({}, '', url);
  }
  function restore() {
    if (!model) return;
    const params = new URLSearchParams(location.search);
    route = Object.fromEntries(routeKeys.filter(key => params.get(key)).map(key => [key, params.get(key)]));
    compare = [...new Set((params.get('compare') || '').split(','))].filter(id => model.byId.has(id)).slice(0, 4);
    paperId = model.byId.has(params.get('paper')) ? params.get('paper') : null;
    page = 1;
    $('#query').value = route.q || '';
    $('#sort').value = route.sort || 'relevance';
    document.querySelectorAll('[data-facet]').forEach(input => { input.value = route[input.dataset.facet] || ''; });
    render();
    if (paperId) showPaper(paperId);
    else dismissPaper();
  }
  function changeFilter(key, value, push = true) {
    if (!model) return;
    if (value) route[key] = value;
    else delete route[key];
    page = 1;
    write(push);
    render();
  }

  function renderFacets() {
    const host = $('#facets');
    for (const [key, label, field] of facetDefs) {
      const wrap = document.createElement('label');
      wrap.className = 'facet';
      wrap.append(document.createTextNode(label));
      const select = document.createElement('select');
      select.dataset.facet = key;
      select.setAttribute('aria-label', label);
      select.add(new Option('全部', ''));
      for (const option of model.facets[field]) {
        const caption = key === 'component' ? componentLabels[option.value] : option.label;
        select.add(new Option(`${caption}（${option.count}）`, option.value));
      }
      select.addEventListener('change', () => changeFilter(key, select.value));
      wrap.append(select);
      host.append(wrap);
    }
  }

  function domainBadges(paper) {
    return list(paper.component_ids).map(id => `<span class="badge domain-${e(id)}">${e(componentLabels[id])}</span>`).join('');
  }
  function badges(paper) {
    return domainBadges(paper) +
      [paper.region_label, ...list(paper.paper_types)].filter(Boolean).map(value => `<span class="badge">${e(value)}</span>`).join('') +
      (paper.evidence_coverage?.article ? '<span class="badge badge-evidence">正文定位</span>' : '') +
      (paper.evidence_coverage?.quantitative ? '<span class="badge badge-evidence">结构化定量</span>' : '') +
      [...list(paper.methods_normalized), ...list(paper.software_normalized)].map(value => `<span class="badge badge-method">${e(value)}</span>`).join('');
  }
  function compareButton(id) {
    const active = compare.includes(id);
    return `<button type="button" class="compare-toggle" data-compare="${e(id)}" aria-pressed="${active}" ${compare.length === 4 && !active ? 'disabled' : ''}>${active ? '移出对比' : '加入对比'}</button>`;
  }
  function resultCard(paper) {
    return `<article class="paper-card">
      <div class="card-top"><div class="badges">${badges(paper)}</div><span class="mono">${e(paper.year)}</span></div>
      <h2><a href="${e(urlFor(paper.id))}" data-paper-link="${e(paper.id)}">${e(paper.title)}</a>${paper.title_zh && paper.title_zh !== paper.title ? `<small>${e(paper.title_zh)}</small>` : ''}</h2>
      <p class="paper-meta">${e([joined(list(paper.authors).slice(0, 3)), paper.journal].filter(Boolean).join(' · '))}</p>
      <p class="paper-summary">${e(paper.summary)}</p>
      ${paper.retrieval?.reason ? `<p class="paper-match">${e(paper.retrieval.reason)}</p>` : ''}
      <div class="paper-footer"><span class="mono">${e(paper.doi)}</span>${compareButton(paper.id)}</div>
    </article>`;
  }
  function render() {
    const found = model.query(route);
    rows = found.rows;
    const pageSize = 18;
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    $('#result-count').textContent = `${rows.length} 篇论文`;
    $('#active-filters').textContent = found.expandedTerms.length ? `检索扩展 · ${found.expandedTerms.join('、')}` : '';
    page = Math.min(page, pages);
    results.innerHTML = rows.slice((page - 1) * pageSize, page * pageSize).map(resultCard).join('');
    $('#empty-state').hidden = rows.length !== 0;
    $('#pager').innerHTML = pages > 1 ? `
      <button type="button" data-page="${page - 1}" ${page === 1 ? 'disabled' : ''}>上一页</button>
      <span>${page} / ${pages}</span>
      <button type="button" data-page="${page + 1}" ${page === pages ? 'disabled' : ''}>下一页</button>` : '';
    $('#compare-tray').hidden = !compare.length;
    $('#compare-count').textContent = compare.length;
    $('#compare-open').disabled = compare.length < 2;
  }

  const external = (url, label) => {
    const href = window.WorkbenchModel.safeLink(url);
    return href ? `<a href="${e(href)}" target="_blank" rel="noopener noreferrer">${e(label)}</a>` : '';
  };
  const items = (values, renderItem) => {
    const entries = list(values).map(renderItem).filter(Boolean);
    return entries.length ? `<ul class="evidence-list">${entries.map(value => `<li>${value}</li>`).join('')}</ul>` : '';
  };
  const plain = values => items(values, e);
  const block = (label, value) => value ? `<div class="evidence-item"><b>${e(label)}</b><span>${e(value)}</span></div>` : '';
  const section = (title, body) => body ? `<section class="evidence-section"><h3>${title}</h3>${body}</section>` : '';
  const parameterModel = paper => joined([paper.functional, paper.force_field, paper.mlip_architecture].filter(Boolean));
  const metricValue = metric => [metric.value, metric.unit].filter(v => v != null && v !== '').join(' ');
  const metricContext = metric => {
    const conditions = [metric.conditions, metric.comparison].filter(Boolean).join(' · ');
    const location = external(metric.source, metric.locator) || e([metric.source, metric.locator].join(' · '));
    return `${conditions ? `<small>${e(conditions)}</small>` : ''}<small>${location}</small>`;
  };
  const doiUrl = doi => doi ? `https://doi.org/${doi.split('/').map(encodeURIComponent).join('/')}` : '';

  function insights(paper, name) {
    return items(paper.insight?.sections?.[name], item => {
      const refs = list(item.source_refs).map(id => paper.insight.sources?.find(source => source.id === id)).filter(Boolean);
      return `${e(item.text)}${item.kind === 'reading_guide' ? '<small>阅读建议</small>' : ''}${refs.map(ref => `<small>${external(ref.url, ref.locator)}</small>`).join('')}`;
    });
  }
  function localLinks(paper) {
    const id = encodeURIComponent(paper.id);
    const zotero = local?.zotero?.[String(paper.doi || '').toLowerCase()];
    const validKey = key => typeof key === 'string' && /^[A-Z0-9]{8}$/i.test(key);
    const pdf = local?.literature?.[paper.id]?.status === 'downloaded';
    return [
      pdf ? `<a href="/local-pdf/${id}.pdf" target="_blank" rel="noopener">打开本地 PDF</a>` : '',
      validKey(zotero?.attachment_key) ? `<a href="zotero://open-pdf/library/items/${zotero.attachment_key}">在 Zotero 打开原文</a>` :
        validKey(zotero?.item_key) ? `<a href="zotero://select/library/items/${zotero.item_key}">在 Zotero 查看条目</a>` : '',
    ].join('');
  }
  function anchors(paper, evidence) {
    const hit = rows.find(row => row.id === paper.id)?.retrieval?.reason;
    const pdf = local?.literature?.[paper.id]?.status === 'downloaded';
    const locators = items(list(local?.methods?.[paper.id]?.evidence).slice(0, 12), item => {
      if (!Number.isInteger(Number(item.page)) || Number(item.page) < 1) return '';
      const label = `PDF 第 ${Number(item.page)} 页`;
      const link = pdf ? external(`/local-pdf/${encodeURIComponent(paper.id)}.pdf#page=${Number(item.page)}`, label) : label;
      return `${e(item.label_zh)} · ${link}<small>${e(item.signal)}</small>`;
    });
    return (hit ? `<p>${e(hit)}</p>` : '') +
      items(evidence, item => `${e(item.claim)}<small>${e(joined([item.basis, item.strength]))}</small>`) +
      items(paper.insight?.sources, ref => external(ref.url, ref.locator)) + locators;
  }
  function related(paper) {
    const routeData = sources.route;
    const nodes = [...list(routeData?.stages).map(node => ['stage', node]), ...list(routeData?.frontiers).map(node => ['frontier', node])];
    const links = nodes.filter(([, node]) => node.paper_ids?.includes(paper.id))
      .map(([prefix, node]) => `<a href="./learning-route.html#${prefix}-${encodeURIComponent(node.id)}">${e(node.label || node.id)}</a>`);
    const relations = items(paper.relations, relation => {
      const target = model.byId.get(relation.target);
      return target
        ? `${e(relation.source)} · <a href="${e(urlFor(target.id))}" data-paper-link="${e(target.id)}">${e(target.title)}</a>`
        : e(joined([relation.source, relation.relation, relation.target]));
    });
    return relations + (links.length ? `<div class="drawer-actions">${links.join('')}</div>` : '') +
      `<div class="drawer-actions">${compareButton(paper.id)}</div>`;
  }

  function metricTable(metrics) {
    if (!metrics.length) return '<p>暂无逐项定位的结构化数值。</p>';
    return `<table class="metric-table"><thead><tr><th scope="col">指标</th><th scope="col">数值</th><th scope="col">条件与来源</th></tr></thead>
      <tbody>${metrics.map(metric => `<tr><th scope="row">${e(metric.label)}</th><td class="mono">${e(metricValue(metric))}</td>
      <td>${metricContext(metric)}</td></tr>`).join('')}</tbody></table>`;
  }

  function lammpsLessonLink(paper, software) {
    const usesLammps = list(software).some(value => String(value).toUpperCase() === 'LAMMPS');
    if (!usesLammps) return '';
    return `<p><a href="./learn.html?course=md#tutorials">打开 MD / LAMMPS 学习课 →</a> · <a href="./library.html?software=LAMMPS&evidence=article">查看正文有定位的 LAMMPS 论文</a></p>`;
  }

  function evidenceHtml({paper, sections: s}) {
    const metrics = s.observables.metrics;
    const takeaway = metrics[0];
    return [
      section('题录与来源', `<h4>${e(paper.title)}</h4>${paper.title_zh && paper.title_zh !== paper.title ? `<p>${e(paper.title_zh)}</p>` : ''}
        <p>${e(joined(paper.authors))}<br>${e([paper.journal, paper.year].filter(Boolean).join(' · '))}</p>
        <div class="badges">${badges(paper)}</div><div class="drawer-actions">${external(doiUrl(paper.doi) || paper.url, paper.doi || '出版页')}${localLinks(paper)}
        <button type="button" data-copy="bibtex">复制 BibTeX</button></div>`),
      section('要点与定量结论', `<p>${e(paper.summary)}</p>${insights(paper, 'findings')}${takeaway ? `<p class="metric">${e(takeaway.label)} · ${e(metricValue(takeaway))}</p>` : ''}`),
      section('材料体系与电池组件', domainBadges(paper) + plain(s.material.systems) + insights(paper, 'systems')),
      section('计算协议', `<div class="evidence-grid">${block('方法', joined(paper.methods))}${block('软件', joined(s.protocol.software))}${block('泛函、力场或模型', parameterModel(paper))}</div>` +
        lammpsLessonLink(paper, s.protocol.software) + insights(paper, 'methods') + insights(paper, 'conditions') + plain(s.protocol.steps)),
      section('观测量与基准', metricTable(metrics)),
      section('证据锚点与命中原因', anchors(paper, s.evidence.evidence)),
      section('局限与复现', (paper.scope_note ? `<p>${e(paper.scope_note)}</p>` : '') + insights(paper, 'limits') + insights(paper, 'reproduction') +
        items(paper.resources, resource => external(resource.url, resource.label))),
      section('相关文献、学习路线与操作', related(paper)),
    ].join('');
  }

  function showPaper(id, push = false) {
    const card = model?.card(id);
    if (!card) return;
    if (!drawer.open) previousFocus = document.activeElement;
    const body = $('#drawer-body');
    const samePaper = drawer.open && paperId === id;
    const scroll = samePaper ? body.scrollTop : 0;
    paperId = id;
    if (push) write(true);
    body.innerHTML = evidenceHtml(card);
    body.scrollTop = scroll;
    if (!samePaper) {
      $('#drawer-copy').hidden = true;
      $('#drawer-feedback').textContent = '';
    }
    const index = rows.findIndex(row => row.id === id);
    $('#drawer-prev').disabled = index <= 0;
    $('#drawer-next').disabled = index < 0 || index + 1 === rows.length;
    if (!drawer.open) drawer.showModal();
  }
  function dismissPaper(update = false) {
    if (drawer.open) drawer.close();
    paperId = null;
    if (update) write();
    if (previousFocus?.isConnected) previousFocus.focus();
    previousFocus = null;
  }
  function adjacentPaper(delta) {
    const index = rows.findIndex(row => row.id === paperId);
    const next = index >= 0 ? rows[index + delta] : null;
    if (next) showPaper(next.id, true);
  }

  function showComparison() {
    if (compare.length < 2) return;
    const cards = compare.map(id => model.card(id));
    const cell = value => e(value || '暂无资料');
    const fields = [
      ['材料体系', card => cell(joined(card.sections.material.systems))],
      ['方法与软件', card => cell(joined([...new Set([...list(card.paper.methods), ...card.sections.protocol.software])]))],
      ['泛函、力场或模型', card => cell(parameterModel(card.paper))],
      ['关键指标与条件', card => items(card.sections.observables.metrics, metric =>
        `<strong>${e(metric.label)}</strong> <code>${e(metricValue(metric))}</code>${metricContext(metric)}`
      ) || '暂无资料'],
      ['局限性', card => cell(joined([...new Set([card.paper.scope_note, ...list(card.paper.insight?.sections?.limits).map(item => item.text)].filter(Boolean))]))],
    ];
    $('#compare-body').innerHTML = `<table class="compare-table"><thead><tr><th scope="col">比较维度</th>
      ${cards.map(card => `<th scope="col">${e(card.paper.title_zh || card.paper.title)}</th>`).join('')}</tr></thead>
      <tbody>${fields.map(([label, value]) => `<tr><th scope="row">${label}</th>${cards.map(card => `<td>${value(card)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    matrix.showModal();
  }

  async function copy(value, message) {
    if (!value) return;
    const feedback = $('#drawer-feedback');
    try {
      await window.CitationTools.copy(value);
      feedback.textContent = message;
    } catch (_) {
      const area = $('#drawer-copy');
      area.hidden = false;
      area.value = value;
      area.focus();
      area.select();
      feedback.textContent = '请复制已选中的文字。';
    }
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-paper-link], [data-compare], [data-page], [data-copy]');
    if (!trigger || !model) return;
    const {paperLink, compare:id, page:target, copy:format} = trigger.dataset;
    if (paperLink && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      showPaper(paperLink, true);
    } else if (id) {
      if (!model.byId.has(id)) return;
      compare = compare.includes(id) ? compare.filter(value => value !== id) : [...compare, id].slice(0, 4);
      write();
      render();
      if (drawer.open) showPaper(paperId);
      const area = drawer.open ? drawer : results;
      [...area.querySelectorAll('[data-compare]')].find(button => button.dataset.compare === id)?.focus({preventScroll:true});
    } else if (target) {
      page = Number(target);
      render();
      $('#result-count').scrollIntoView({block:'start'});
      results.querySelector('a')?.focus({preventScroll:true});
    } else if (format === 'bibtex') {
      copy(window.CitationTools?.bibtex(model.byId.get(paperId)), '已复制 BibTeX。');
    }
  });
  $('#query').addEventListener('input', event => changeFilter('q', event.target.value.trim(), false));
  $('#sort').addEventListener('change', event => changeFilter('sort', event.target.value));
  $('#clear-filters').addEventListener('click', () => {
    if (!model) return;
    route = {};
    write(true);
    restore();
  });
  $('#empty-clear').addEventListener('click', () => $('#clear-filters').click());
  $('#drawer-close').addEventListener('click', () => dismissPaper(true));
  $('#drawer-prev').addEventListener('click', () => adjacentPaper(-1));
  $('#drawer-next').addEventListener('click', () => adjacentPaper(1));
  $('#share-paper').addEventListener('click', () => copy(location.href, '已复制分享链接。'));
  $('#compare-open').addEventListener('click', showComparison);
  $('#compare-close').addEventListener('click', () => matrix.close());
  $('#compare-clear').addEventListener('click', () => { compare = []; write(); render(); });
  drawer.addEventListener('cancel', event => { event.preventDefault(); dismissPaper(true); });
  drawer.addEventListener('click', event => { if (event.target === drawer) dismissPaper(true); });
  drawer.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.target.closest('input, textarea, select, [contenteditable]')) return;
    const delta = {ArrowUp:-1, ArrowLeft:-1, ArrowDown:1, ArrowRight:1}[event.key];
    if (delta) { event.preventDefault(); adjacentPaper(delta); }
  });
  window.addEventListener('popstate', restore);
  start();
})();
