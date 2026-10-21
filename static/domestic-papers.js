(() => {
  const search = document.querySelector('#domestic-search'), category = document.querySelector('#domestic-category'), topic = document.querySelector('#domestic-topic'), count = document.querySelector('#domestic-count'), empty = document.querySelector('#domestic-empty');
  const cards = [...document.querySelectorAll('.domestic-card')];
  const stages = [...document.querySelectorAll('.domestic-stage')], frontierGroups = [...document.querySelectorAll('.domestic-frontier-group')];
  const defaultOpen = new Map([...stages, ...frontierGroups].map(node => [node, !!node.open]));
  const apply = () => { const q=(search.value||'').trim().toLocaleLowerCase(), c=category.value, t=topic.value; let visible=0;
    cards.forEach(card => { const ok=(!q || (card.dataset.search||'').toLocaleLowerCase().includes(q)) && (c==='all'||card.dataset.category===c) && (t==='all'||card.dataset.topic===t); card.hidden=!ok; if(ok) visible++; });
    const active = !!q || c !== 'all' || t !== 'all';
    frontierGroups.forEach(group => {
      const links = group.querySelectorAll ? [...group.querySelectorAll('.domestic-frontier-link')] : [];
      links.forEach(link => {
        const target = document.getElementById ? document.getElementById(link.dataset.targetCard || '') : null;
        const targetEligible = target && (c==='all'||target.dataset.category===c) && (t==='all'||target.dataset.topic===t);
        link.hidden = !(targetEligible && !target.hidden);
      });
      const matching = links.some(link => !link.hidden);
      group.hidden = !matching;
      group.open = active ? matching : defaultOpen.get(group);
    });
    stages.forEach(stage => {
      const matching = stage.querySelector && stage.querySelector('.domestic-card:not([hidden])');
      const visibleFrontier = stage.querySelector && stage.querySelector('.domestic-frontier-group:not([hidden])');
      stage.hidden = !matching && !visibleFrontier;
      stage.open = active ? !!(matching || visibleFrontier) : defaultOpen.get(stage);
    });
    document.querySelectorAll('.domestic-group').forEach(group => {
      const hasCard = group.querySelector('.domestic-card:not([hidden])');
      const hasRouteMatch = group.dataset.group === 'chinese_original' && document.querySelector && document.querySelector('.domestic-stage:not([hidden]), .domestic-frontier-group:not([hidden])');
      group.hidden = !hasCard && !hasRouteMatch;
    });
    count.textContent=`显示 ${visible} / ${cards.length} 篇`; empty.hidden=visible!==0;
  };
  [search,category,topic].forEach(node => node.addEventListener('input', apply));
  document.querySelector('#domestic-reset').addEventListener('click', () => { search.value=''; category.value='all'; topic.value='all'; apply(); }); apply();
  if (document.addEventListener) document.addEventListener('click', event => {
    const link = event.target && event.target.closest ? event.target.closest('.domestic-frontier-link') : null;
    if (!link || !document.getElementById) return;
    const target = document.getElementById(link.dataset.targetCard || '');
    let node = target;
    while (node) { if (node.tagName === 'DETAILS') node.open = true; node = node.parentElement; }
  });
})();
