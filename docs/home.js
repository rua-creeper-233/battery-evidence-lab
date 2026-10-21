(() => {
  const panels = [...document.querySelectorAll('[data-home-panel]')];
  const tabs = [...document.querySelectorAll('[data-home-tab]')];
  const valid = new Set(panels.map(panel => panel.dataset.homePanel));
  function activate(name, updateHash = true) {
    const target = valid.has(name) ? name : 'research-question';
    panels.forEach(panel => {
      const selected = panel.dataset.homePanel === target;
      panel.classList.toggle('is-active', selected);
      panel.hidden = !selected;
    });
    tabs.forEach(tab => {
      const selected = tab.dataset.homeTab === target;
      tab.setAttribute('aria-selected', String(selected));
      tab.setAttribute('tabindex', selected ? '0' : '-1');
    });
    if (updateHash && location.hash !== `#${target}`) history.pushState(null, '', `#${target}`);
  }
  tabs.forEach(tab => tab.addEventListener('click', event => { event.preventDefault(); activate(tab.dataset.homeTab); }));
  tabs.forEach((tab, index) => tab.addEventListener('keydown', event => {
    const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length
      : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length
      : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    tabs[next].focus();
    activate(tabs[next].dataset.homeTab);
  }));
  const initial = location.hash.slice(1);
  activate(valid.has(initial) ? initial : 'research-question', false);
  window.addEventListener('hashchange', () => activate(location.hash.slice(1), false));
  window.addEventListener('popstate', () => activate(location.hash.slice(1), false));

  const robot = document.createElement('div');
  robot.className = 'robot-widget';
  robot.innerHTML = `<div class="robot-bubble" hidden aria-live="polite"></div><div class="robot-actions" hidden><button class="secondary" type="button" data-robot-next>换一篇</button><button class="secondary" type="button" data-robot-close>关闭</button></div><button class="robot-button" type="button" aria-label="随机查看一篇论文"><svg viewBox="0 0 48 48" aria-hidden="true"><rect x="10" y="14" width="28" height="23" rx="8" fill="#d9efe5" stroke="currentColor" stroke-width="2"/><path d="M24 14V8m-4 0h8M16 25h1m14 0h1M18 32h12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="18" cy="25" r="2" fill="currentColor"/><circle cx="30" cy="25" r="2" fill="currentColor"/></svg></button>`;
  document.body.appendChild(robot);
  const button = robot.querySelector('.robot-button');
  const bubble = robot.querySelector('.robot-bubble');
  const actions = robot.querySelector('.robot-actions');
  let selectedId = null; let firstClick = true;
  const catalogReady = window.setInterval(() => {
    if (papers().length) { button.disabled = false; window.clearInterval(catalogReady); }
  }, 400);
  function papers() { return Array.isArray(window.state?.papers) ? window.state.papers : []; }
  function choose() {
    const available = papers().filter(p => p && p.id && p.id !== selectedId);
    if (!available.length) return null;
    return available[Math.floor(Math.random() * available.length)];
  }
  function show(paper) {
    if (!paper) { button.disabled = !papers().length; firstClick = true; bubble.hidden = false; bubble.textContent = papers().length ? '暂无可重复推荐的论文。' : '论文库尚未加载。'; actions.hidden = true; return; }
    selectedId = paper.id;
    const title = paper.title || paper.role || paper.id;
    const zhTitle = paper.title_zh || window.LabUI?.titleZh?.(paper) || '';
    const subtitle = zhTitle ? `；${zhTitle}` : '';
    bubble.innerHTML = `${escapeText(title)}${escapeText(subtitle)}${paper.year ? ` · ${escapeText(String(paper.year))}` : ''}`;
    bubble.hidden = false; actions.hidden = false;
  }
  function escapeText(value) { const span = document.createElement('span'); span.textContent = value; return span.innerHTML; }
  button.addEventListener('click', () => {
    if (firstClick) { firstClick = false; show(choose()); return; }
    if (selectedId && typeof window.showPaper === 'function') window.showPaper(selectedId);
  });
  robot.querySelector('[data-robot-next]').addEventListener('click', () => show(choose()));
  robot.querySelector('[data-robot-close]').addEventListener('click', () => { bubble.hidden = true; actions.hidden = true; firstClick = true; });

  const modal = document.querySelector('#modal');
  const modalClose = document.querySelector('#close');
  let modalReturnFocus = null;
  if (modal && modalClose) {
    const observer = new MutationObserver(() => {
      const open = modal.classList.contains('open');
      modal.setAttribute('aria-hidden', String(!open));
      if (open) { modalReturnFocus = document.activeElement; modalClose.focus(); }
    });
    observer.observe(modal, {attributes: true, attributeFilter: ['class']});
    modal.addEventListener('keydown', event => {
      if (event.key === 'Escape') { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); modalReturnFocus?.focus?.(); }
    });
    modalClose.addEventListener('click', () => { modal.setAttribute('aria-hidden', 'true'); modalReturnFocus?.focus?.(); });
  }
})();
