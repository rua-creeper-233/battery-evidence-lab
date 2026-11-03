/* Shared publication runtime: theme, navigation intent, keyboard affordances and details motion. */
(() => {
  'use strict';
  if (window.__batteryNotebookRuntime) return;
  window.__batteryNotebookRuntime = true;

  const THEME_KEY = 'battery-lab-theme';
  const root = document.documentElement;
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const prefersDark = () => !!media?.matches;
  const readTheme = () => {
    try { const value = localStorage.getItem(THEME_KEY); return ['light', 'dark'].includes(value) ? value : null; } catch (_) { return null; }
  };
  const writeTheme = (value) => { try { localStorage.setItem(THEME_KEY, value); } catch (_) {} };
  const applyTheme = (value) => {
    const theme = value === 'dark' || value === 'light' ? value : (prefersDark() ? 'dark' : 'light');
    root.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      const next = theme === 'dark' ? 'light' : 'dark';
      button.title = next === 'dark' ? '切换为深色模式' : '切换为浅色模式';
      button.setAttribute('aria-label', button.title);
      button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
  };
  let preference = readTheme();
  applyTheme(preference);
  document.addEventListener('click', (event) => {
    const button = event.target.closest?.('[data-theme-toggle]');
    if (!button) return;
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    preference = next; writeTheme(next); applyTheme(next);
  });
  const onSystemTheme = () => { if (!preference) applyTheme(); };
  if (media?.addEventListener) media.addEventListener('change', onSystemTheme);
  else media?.addListener?.(onSystemTheme);

  const canPrefetch = () => {
    const connection = navigator.connection;
    return navigator.onLine !== false && !connection?.saveData && connection?.effectiveType !== '2g' && connection?.effectiveType !== 'slow-2g';
  };
  const prefetched = new Set();
  const base = new URL('./', location.href);
  const knownPages = new Set(['', 'index.html', 'future-directions.html', 'ai-battery-applications.html', 'foundations.html', 'learning-route.html', 'domestic-papers.html'].map(page => new URL(page, base).pathname));
  const prefetch = (anchor) => {
    if (!canPrefetch() || !anchor?.href || anchor.target || anchor.hasAttribute('download')) return;
    let url;
    try { url = new URL(anchor.href, location.href); } catch (_) { return; }
    if (url.origin !== location.origin || url.username || url.password || url.search || !knownPages.has(url.pathname)) return;
    if (url.pathname === location.pathname || (url.pathname === base.pathname && location.pathname === base.pathname + 'index.html')) return;
    const key = `${url.origin}${url.pathname}`;
    if (prefetched.has(key)) return;
    prefetched.add(key);
    const link = document.createElement('link');
    link.rel = 'prefetch'; link.as = 'document'; link.href = key;
    link.addEventListener('error', () => prefetched.delete(key), { once: true });
    document.head.appendChild(link);
  };
  const navIntent = event => {
    const anchor = event.target.closest?.('.site-nav a[href]');
    if (anchor) prefetch(anchor);
  };
  document.addEventListener('pointerover', navIntent);
  document.addEventListener('focusin', navIntent);

  const focusHomeContext = () => {
    const pathname = location.pathname;
    const ids = pathname.endsWith('/learning-route.html') ? ['route-search'] : pathname.endsWith('/foundations.html') ? ['search'] : pathname.endsWith('/index.html') || pathname.endsWith('/') ? ['question', 'filter'] : [];
    const visible = (node) => node && node.getClientRects?.().length && !node.closest?.('[hidden], [aria-hidden="true"], .is-hidden, .hidden');
    const node = ids.map((id) => document.getElementById(id)).find(visible) ||
      [...document.querySelectorAll('input[type="search"]')].find(visible);
    if (node && typeof node.focus === 'function') { node.focus(); return true; }
    return false;
  };
  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const target = event.target;
    if (target?.isContentEditable || target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="dialog"], dialog, .modal.open, .modal.is-open')) return;
    if ([...document.querySelectorAll('.modal.open, dialog[open], [role="dialog"]:not([hidden])')].some(node => node.getClientRects().length)) return;
    if (focusHomeContext()) event.preventDefault();
  });

  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  const motions = new WeakMap();
  const animateDetails = (details, closing = false) => {
    if (!details || reducedMotion() || typeof details.animate !== 'function') return false;
    const summary = details.querySelector(':scope > summary');
    if (!summary) return false;
    const previous = motions.get(details);
    const start = details.getBoundingClientRect().height;
    if (previous) { previous.animation.onfinish = null; previous.animation.cancel(); }
    const overflow = previous ? previous.overflow : details.style.overflow;
    details.open = true;
    const end = closing ? summary.getBoundingClientRect().height : details.getBoundingClientRect().height;
    if (!start || !end || start === end) { details.open = !closing; details.style.overflow = overflow; motions.delete(details); return true; }
    details.style.overflow = 'hidden';
    const animation = details.animate([{ height: `${start}px`, opacity: closing ? 1 : .7 }, { height: `${end}px`, opacity: closing ? .7 : 1 }], { duration: 180, easing: 'ease-out' });
    motions.set(details, { animation, overflow, closing });
    animation.onfinish = () => { details.open = !closing; details.style.overflow = overflow; motions.delete(details); };
    return true;
  };
  document.addEventListener('click', (event) => {
    const summary = event.target.closest?.('summary');
    if (!summary || event.defaultPrevented || event.target.closest?.('a,button,input,select,textarea')) return;
    const details = summary.parentElement;
    if (!details || details.tagName !== 'DETAILS' || reducedMotion() || typeof details.animate !== 'function') return;
    const active = motions.get(details);
    const closing = active ? !active.closing : details.open;
    if (animateDetails(details, closing)) event.preventDefault();
  }, true);
  window.NotebookRuntime = { applyTheme, prefetch, focusHomeContext, animateDetails };
})();
