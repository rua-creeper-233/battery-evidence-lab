(() => {
  const cards = [...document.querySelectorAll('.stage-card, .frontier-card')];
  const search = document.querySelector('#route-search');
  const filter = document.querySelector('#stage-filter');
  const count = document.querySelector('#route-count');
  const empty = document.querySelector('#route-empty');
  const normalize = (value) => String(value || '').trim().toLocaleLowerCase();
  const templates = (card) => [...card.querySelectorAll('template.paper-template')];
  const templateMatches = (node, query) => normalize(node.dataset.search || '').includes(query);
  const mountTemplates = (card, query = '') => {
    templates(card).forEach((template) => {
      const ownerFrontier = template.closest('.frontier-card');
      const ownerReference = template.closest('.reference-group');
      if ((ownerFrontier && ownerFrontier !== card && !ownerFrontier.open) || (ownerReference && ownerReference !== card && !ownerReference.open)) return;
      if (query && !templateMatches(template, query)) return;
      const article = template.content?.firstElementChild;
      if (article) {
        const mounted = article.cloneNode(true);
        mounted.dataset.search = template.dataset.search || '';
        template.replaceWith(mounted);
      }
    });
  };
  const conceptText = (card) => {
    const copy = card.cloneNode(true);
    copy.querySelectorAll('.paper-card, .reference-paper-card, .paper-template, .citations, .reference-groups, .frontier-card').forEach((node) => node.remove());
    return normalize(copy.textContent);
  };
  const paperMatch = (card, query) => [
    ...card.querySelectorAll('.paper-card[data-search], .reference-paper-card[data-search]'),
    ...card.querySelectorAll('template.paper-template'),
  ].some((node) => templateMatches(node, query));
  const ownStageMatch = (card, stage) => stage === 'all' || card.dataset.stage === stage || (stage === 'frontier' && Boolean(card.dataset.frontier));
  const matches = (card) => {
    const query = normalize(search.value);
    const stage = filter.value;
    if (!ownStageMatch(card, stage)) return false;
    if (!query) return true;
    if (conceptText(card).includes(query) || paperMatch(card, query)) return true;
    return [...card.querySelectorAll('.frontier-card')].some((child) => ownStageMatch(child, stage) && matches(child));
  };
  const refresh = () => {
    const query = normalize(search.value);
    cards.forEach((card) => {
      if (query && matches(card)) mountTemplates(card, query);
      else if (card.open) mountTemplates(card);
    });
    let visible = 0;
    cards.forEach((card) => { const show = matches(card); card.hidden = !show; if (show) visible += 1; });
    const allPaperNodes = [...document.querySelectorAll('.paper-card[data-paper-id]')];
    const referenceNodes = [...document.querySelectorAll('.reference-paper-card[data-paper-id]')];
    [...allPaperNodes, ...referenceNodes].forEach((node) => { node.hidden = Boolean(query && !normalize(`${node.textContent} ${node.dataset.search}`).includes(query)); });
    document.querySelectorAll('.citations, .reference-group').forEach((section) => {
      const sectionNodes = [...section.querySelectorAll('.paper-card'), ...section.querySelectorAll('.reference-paper-card'), ...section.querySelectorAll('template.paper-template')];
      section.hidden = Boolean(query) && !sectionNodes.some((node) => node.matches?.('template.paper-template') ? templateMatches(node, query) : !node.hidden);
    });
    const allNodes = [...document.querySelectorAll('.paper-card[data-paper-id]'), ...document.querySelectorAll('.reference-paper-card[data-paper-id]'), ...document.querySelectorAll('template.paper-template')];
    const uniquePaperIds = new Set(allNodes.map((node) => node.dataset.paperId));
    const matchingNodes = allNodes.filter((node) => (!query || templateMatches(node, query)) && !node.closest('details[hidden]'));
    const visiblePaperIds = new Set(matchingNodes.map((node) => node.dataset.paperId));
    count.textContent = `显示 ${visible} / ${cards.length} 个路线分支 · 论文 ${visiblePaperIds.size}/${uniquePaperIds.size} 篇 · 匹配引用 ${matchingNodes.length} 条`;
    empty.hidden = visible !== 0;
  };
  let refreshTimer = null;
  const scheduleRefresh = () => {
    if (typeof setTimeout !== 'function') { refresh(); return; }
    if (refreshTimer !== null) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => { refreshTimer = null; refresh(); }, 150);
  };
  const readHash = () => { const encoded = location.hash.slice(1); if (!encoded) return null; try { return decodeURIComponent(encoded); } catch (_) { return null; } };
  const openHashTarget = () => {
    const target = readHash();
    if (!target) return;
    search.value = ''; filter.value = 'all';
    const template = [...document.querySelectorAll('template.paper-template')].find((node) => node.content?.firstElementChild?.id === target);
    if (template) {
      let parent = template.closest('details');
      while (parent) { parent.open = true; mountTemplates(parent); parent = parent.parentElement?.closest('details'); }
    }
    refresh();
    const node = document.getElementById(target);
    if (!node) return;
    let parent = node.closest('details');
    while (parent) { parent.open = true; parent = parent.parentElement?.closest('details'); }
    if (node.matches('details')) node.open = true;
    if (typeof node.focus === 'function') node.focus({ preventScroll: true });
    if (typeof node.scrollIntoView === 'function') node.scrollIntoView({ block: 'start' });
  };
  search.addEventListener('input', scheduleRefresh);
  filter.addEventListener('change', scheduleRefresh);
  document.querySelector('#expand-visible').addEventListener('click', () => {
    cards.forEach((card) => { if (!card.hidden) { card.open = true; mountTemplates(card); } });
    document.querySelectorAll('.reference-group').forEach((group) => { if (!group.hidden && !group.closest('details[hidden]')) { group.open = true; mountTemplates(group); } });
    refresh();
  });
  document.querySelector('#collapse-visible').addEventListener('click', () => {
    cards.forEach((card) => { if (!card.hidden) card.open = false; });
    document.querySelectorAll('.reference-group').forEach((group) => { if (!group.hidden) group.open = false; });
  });
  document.querySelectorAll('details.stage-card, details.frontier-card, details.reference-group').forEach((details) => {
    details.addEventListener?.('toggle', () => { if (details.open) { mountTemplates(details); refresh(); } });
  });
  window.addEventListener('hashchange', openHashTarget);
  refresh();
  openHashTarget();
})();
