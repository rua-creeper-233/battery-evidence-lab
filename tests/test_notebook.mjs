import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../static/notebook.js', import.meta.url), 'utf8');

function loadNotebook({ pathname = '/battery-evidence-lab/index.html', storage = {}, storageThrows = false, prefersDark = true, reducedMotion = false, online = true } = {}) {
  const listeners = new Map();
  const links = [];
  const nodes = new Map();
  const root = { dataset: {} };
  const media = { matches: prefersDark, addEventListener(type, fn) { this.change = fn; }, change: null };
  const reduceMedia = { matches: reducedMotion };
  const document = {
    documentElement: root,
    head: { appendChild(node) { links.push(node); } },
    addEventListener(type, fn) { const fns = listeners.get(type) ?? []; fns.push(fn); listeners.set(type, fns); },
    querySelectorAll(selector) {
      if (selector === '[data-theme-toggle]') return [];
      if (selector === 'input[type="search"]') return [...nodes.values()].filter((node) => node.search);
      if (selector === '.modal.open, dialog[open], [role="dialog"]:not([hidden])') return [];
      return [];
    },
    getElementById(id) { return nodes.get(id) ?? null; },
    createElement() { return { addEventListener() {}, rel: '', as: '', href: '' }; },
  };
  const localStorage = {
    getItem(key) { if (storageThrows) throw new Error('storage unavailable'); return storage[key] ?? null; },
    setItem(key, value) { if (storageThrows) throw new Error('storage unavailable'); storage[key] = value; },
  };
  const window = { matchMedia(query) { return query.includes('reduced-motion') ? reduceMedia : media; } };
  const context = vm.createContext({ window, document, localStorage, navigator: { onLine: online }, location: { pathname, href: `https://lab.test${pathname}`, origin: 'https://lab.test' }, URL, console, setTimeout });
  vm.runInContext(source, context);
  return { context, listeners, links, media, root, nodes, document };
}

function eventTarget(element) { return { closest(selector) { return selector === 'summary' ? element : null; } }; }

test('theme falls back safely when storage is unavailable and follows system changes', () => {
  const env = loadNotebook({ storageThrows: true, prefersDark: true });
  assert.equal(env.root.dataset.theme, 'dark');
  env.context.window.NotebookRuntime.applyTheme('light');
  assert.equal(env.root.dataset.theme, 'light');
  env.media.matches = false;
  env.media.change();
  assert.equal(env.root.dataset.theme, 'light', 'explicit theme should survive system changes');
  const system = loadNotebook({ storageThrows: true, prefersDark: true });
  system.media.matches = false;
  system.media.change();
  assert.equal(system.root.dataset.theme, 'light');
});

test('prefetch is scoped to the deployed project base and filters unsafe or irrelevant links', () => {
  const env = loadNotebook();
  const prefetch = env.context.window.NotebookRuntime.prefetch;
  const anchor = (href, extra = {}) => ({ href, target: '', hasAttribute: () => false, ...extra });
  prefetch(anchor('https://lab.test/battery-evidence-lab/future-directions.html'));
  prefetch(anchor('https://lab.test/future-directions.html'));
  prefetch(anchor('https://lab.test/battery-evidence-lab/future-directions.html?utm_source=x'));
  prefetch(anchor('https://user:pass@lab.test/battery-evidence-lab/future-directions.html'));
  prefetch(anchor('https://evil.test/battery-evidence-lab/future-directions.html'));
  prefetch(anchor('https://lab.test/battery-evidence-lab/index.html'));
  prefetch(anchor('https://lab.test/battery-evidence-lab/future-directions.html', { target: '_blank' }));
  prefetch(anchor('https://lab.test/battery-evidence-lab/future-directions.html', { hasAttribute: (name) => name === 'download' }));
  prefetch(anchor('https://lab.test/battery-evidence-lab/future-directions.html'));
  assert.equal(env.links.length, 1);
  assert.equal(env.links[0].href, 'https://lab.test/battery-evidence-lab/future-directions.html');
  const offline = loadNotebook({ online: false });
  offline.context.window.NotebookRuntime.prefetch(anchor('https://lab.test/battery-evidence-lab/foundations.html'));
  assert.equal(offline.links.length, 0);
});

test('slash shortcut focuses visible search context and ignores editable or modal targets', () => {
  const env = loadNotebook();
  const search = { search: true, focused: false, getClientRects: () => [{}], closest: () => null, focus() { this.focused = true; } };
  env.nodes.set('question', { getClientRects: () => [], closest: () => null });
  env.nodes.set('filter', search);
  const keydown = env.listeners.get('keydown')[0];
  const makeKey = (target) => ({ key: '/', target, defaultPrevented: false, isComposing: false, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, preventDefault() { this.prevented = true; } });
  const editable = makeKey({ isContentEditable: true, closest: () => null });
  keydown(editable);
  assert.equal(editable.prevented, undefined);
  const modal = makeKey({ isContentEditable: false, closest: (selector) => selector.includes('[role="dialog"]') ? {} : null });
  keydown(modal);
  assert.equal(modal.prevented, undefined);
  const normal = makeKey({ isContentEditable: false, closest: () => null });
  keydown(normal);
  assert.equal(normal.prevented, true);
  assert.equal(search.focused, true);
});

function makeDetails({ open = false, height = 100, summaryHeight = 20 } = {}) {
  const details = { tagName: 'DETAILS', open, style: {}, animations: [], getBoundingClientRect: () => ({ height: details.open ? height : summaryHeight }), querySelector: (selector) => selector === ':scope > summary' ? summary : null, animate(keyframes) { const animation = { keyframes, cancelled: false, onfinish: null, cancel() { this.cancelled = true; } }; details.animations.push(animation); return animation; } };
  const summary = { parentElement: details, getBoundingClientRect: () => ({ height: summaryHeight }) };
  return { details, summary };
}

test('details animation handles open, close, cancellation and reduced-motion fallback', () => {
  const env = loadNotebook();
  const click = (pair, listeners = env.listeners) => { const event = { target: eventTarget(pair.summary), defaultPrevented: false, preventDefault() { this.prevented = true; } }; listeners.get('click').at(-1)(event); return event; };
  const opening = makeDetails({ open: false });
  const openEvent = click(opening);
  assert.equal(openEvent.prevented, true);
  assert.equal(opening.details.animations.length, 1);
  opening.details.animations[0].onfinish();
  assert.equal(opening.details.open, true);
  const closeEvent = click(opening);
  assert.equal(closeEvent.prevented, true);
  opening.details.animations[1].onfinish();
  assert.equal(opening.details.open, false);
  const rapid = makeDetails({ open: false });
  click(rapid);
  const first = rapid.details.animations[0];
  click(rapid);
  assert.equal(first.cancelled, true);
  assert.equal(rapid.details.animations.length, 2);
  rapid.details.animations[1].onfinish();
  assert.equal(rapid.details.open, false);
  const reduced = loadNotebook({ reducedMotion: true });
  const fallback = makeDetails({ open: false });
  const event = click(fallback, reduced.listeners);
  assert.equal(event.prevented, undefined);
  assert.equal(fallback.details.animations.length, 0);
  assert.equal(fallback.details.open, false, 'native browser toggle remains responsible for reduced motion');
  assert.equal(env.context.window.NotebookRuntime.animateDetails(null), false);
});

console.log('Notebook runtime: storage fallback, scoped prefetch, shortcut guards, details transitions PASS');
