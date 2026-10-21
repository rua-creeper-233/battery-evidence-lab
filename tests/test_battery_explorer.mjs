import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../static/battery_explorer.js', import.meta.url), 'utf8');
const data = JSON.parse(fs.readFileSync(new URL('../static/data/battery_components.json', import.meta.url), 'utf8'));
const papers = JSON.parse(fs.readFileSync(new URL('../data/papers.json', import.meta.url), 'utf8'));
const api = requireApi();

function requireApi() {
  const module = { exports: {} };
  vm.runInNewContext(source, { module, URL, console });
  return module.exports;
}

assert.deepEqual(Array.from(api.componentIds), ['cathode', 'anode', 'electrolyte', 'separator', 'interface', 'collectors']);
const resolved = api.resolve(data, papers);
assert.equal(resolved.ok, true, resolved.errors?.join('; '));
assert.equal(resolved.components.length, 6);
assert.equal(resolved.components.flatMap((c) => c.papers).length, 39);
assert.equal(new Set(resolved.components.flatMap((c) => c.papers).map((r) => r.paper_id)).size, 37);

function invalid(mutator) {
  const copy = structuredClone(data);
  mutator(copy);
  assert.equal(api.resolve(copy, papers).ok, false);
}
invalid((d) => { d.components[0].id = d.components[1].id; });
invalid((d) => { d.components[0].papers[0].paper_id = 'private-or-unknown'; });
invalid((d) => { d.components[0].papers[0].doi = '10.9999/stale'; });
invalid((d) => { d.components[0].extra = 'unexpected'; });
invalid((d) => { d.components[0].papers[0].relation = 'guessing'; });
invalid((d) => { d.sources[0].url = 'https://evil.example/steal'; });
invalid((d) => { d.sources[0].url = 'javascript:alert(1)'; });
invalid((d) => { d.sources[0].url = 'https://energy.gov/path?q=private'; });
invalid((d) => { d.components[0].papers.push(structuredClone(d.components[0].papers[0])); });
const sparse = structuredClone(data);
sparse.components.find((c) => c.id === 'separator').papers = [];
sparse.components.find((c) => c.id === 'collectors').papers = [];
assert.equal(api.resolve(sparse, papers).ok, true, 'empty separator/collector references are permitted');
assert.ok(resolved.components.flatMap((c) => c.papers).some((r) => r.relation === 'related'));

class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null;
    this.listeners = new Map(); this.attributes = new Map(); this.dataset = {}; this.style = {};
    this.className = ''; this.textContent = ''; this.innerHTML = ''; this.type = '';
    this.classList = { add: (...names) => names.forEach((n) => this._add(n)), remove: (...names) => names.forEach((n) => this._remove(n)), contains: (n) => this.className.split(/\s+/).includes(n), toggle: (name, force) => { const enabled = force === undefined ? !this.className.split(/\s+/).includes(name) : !!force; if (enabled) this._add(name); else this._remove(name); return enabled; } };
  }
  _add(n) { if (!this.className.split(/\s+/).includes(n)) this.className = `${this.className} ${n}`.trim(); }
  _remove(n) { this.className = this.className.split(/\s+/).filter((x) => x && x !== n).join(' '); }
  appendChild(child) { child.parentElement = this; this.children.push(child); return child; }
  removeChild(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); child.parentElement = null; return child; }
  get firstChild() { return this.children[0] ?? null; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener(type, fn) { const list = this.listeners.get(type) ?? []; list.push(fn); this.listeners.set(type, list); }
  removeEventListener(type, fn) { this.listeners.set(type, (this.listeners.get(type) ?? []).filter((x) => x !== fn)); }
  dispatch(type, extra = {}) { for (const fn of [...(this.listeners.get(type) ?? [])]) fn({ target: this, ...extra }); }
  focus() { document.activeElement = this; this.dispatch('focus'); }
  set innerHTML(value) { this._html = String(value); this.children = []; if (this._html.includes('battery-explorer__svg')) { const svg = new El('svg'); svg.className = 'battery-explorer__svg'; for (const id of api.componentIds) { const g = new El('g'); g.setAttribute('data-component', id); g.dataset.component = id; svg.appendChild(g); } this.appendChild(svg); } }
  get innerHTML() { return this._html ?? ''; }
  _all() { return this.children.flatMap((c) => [c, ...c._all()]); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  querySelectorAll(selector) {
    const all = this._all();
    if (selector === '.battery-explorer__svg') return all.filter((n) => n.className.split(/\s+/).includes('battery-explorer__svg'));
    const tag = selector.match(/^[a-z][a-z0-9-]*$/i)?.[0]; if (tag) return all.filter((n) => n.tagName.toLowerCase() === tag.toLowerCase());
    const cls = selector.match(/^\.([\w-]+)$/)?.[1]; if (cls) return all.filter((n) => n.className.split(/\s+/).includes(cls));
    if (selector === '[data-component]') return all.filter((n) => n.dataset.component !== undefined);
    const attr = selector.match(/^\[data-component="([^"]+)"\]$/)?.[1]; if (attr) return all.filter((n) => n.dataset.component === attr);
    return [];
  }
}
const document = { createElement: (tag) => new El(tag), createTextNode: (text) => { const n = new El('#text'); n.textContent = text; return n; } };
const ctx = vm.createContext({ module: { exports: {} }, document, URL, console });
vm.runInContext(source, ctx);
let opens = 0;
const mountTarget = new El('section');
const mounted2 = ctx.module.exports.mount(mountTarget, { data, papers, heading: '安全标题', titleZh: () => '<img onerror=alert(1)>', onOpen: (id) => { opens += 1; opened = id; } });
let opened = null;
const pins = mountTarget.querySelectorAll('.battery-explorer__pin');
assert.equal(pins.length, 6, 'all six components have figure pin buttons');
assert.equal(mountTarget.querySelector('h2').textContent, '安全标题');
assert.doesNotMatch(mountTarget.querySelector('h2').textContent, /function|onerror/);
assert.equal(mountTarget.querySelector('.battery-explorer__paper-open'), null, 'paper list is not shown before diagram selection');
assert.equal(mountTarget.querySelector('aside'), null, 'paper results are not a persistent right sidebar');
assert.equal(mountTarget.querySelectorAll('.battery-explorer__hotspot').length, 0, 'legend labels are static, not extra controls');
const firstPin = pins[0]; const svg = mountTarget.querySelector('.battery-explorer__svg');
firstPin.dispatch('mouseenter'); assert.equal(svg.classList.contains('is-hovering-cathode'), true);
firstPin.dispatch('mouseleave'); assert.equal(svg.classList.contains('is-hovering-cathode'), false);
firstPin.focus(); assert.equal(svg.classList.contains('is-hovering-cathode'), true);
firstPin.dispatch('click');
assert.match(mountTarget.querySelector('h3').textContent, /^正极/);
assert.ok(mountTarget.querySelector('.battery-explorer__paper-open'), 'diagram pin opens the matching paper list below');
assert.equal(mountTarget.querySelector('aside'), null);
assert.equal(mountTarget.querySelector('.battery-explorer__layout').children.at(-1).className, 'battery-explorer__panel');
const firstPaper = mountTarget.querySelector('.battery-explorer__paper-open');
assert.equal(mountTarget.querySelector('.battery-explorer__paper-title-zh').textContent, '<img onerror=alert(1)>');
firstPaper.dispatch('click');
assert.equal(opens, 1); assert.equal(opened, resolved.components[0].papers[0].paper_id, 'paper callback receives canonical paper ID once');
const identity = pins[1]; identity.focus(); identity.dispatch('click');
assert.match(mountTarget.querySelector('h3').textContent, /^负极/);
assert.equal(mountTarget.querySelectorAll('.battery-explorer__pin')[1], identity, 'selection keeps figure button DOM identity');
assert.equal(mountTarget.querySelectorAll('.battery-explorer__pin')[1].getAttribute('aria-pressed'), 'true');
assert.equal(document.activeElement, identity, 'selection keeps focus on the selected figure button');
const stalePaper = mountTarget.querySelector('.battery-explorer__paper-open');
mountTarget.querySelector('.battery-explorer__close-list').dispatch('click');
assert.equal(mountTarget.querySelector('.battery-explorer__paper-open'), null, 'close clears the below-figure list');
assert.equal(document.activeElement, identity, 'close restores focus to selected pin');
stalePaper.dispatch('click'); assert.equal(opens, 1, 'removed paper handlers are inert');
pins[3].dispatch('click');
assert.match(mountTarget.querySelector('.battery-explorer__empty').textContent, /没有已核验/);
mounted2.update({ data: sparse, papers });
assert.equal(mountTarget.querySelector('.battery-explorer__paper-open'), null, 'update resets to unselected state');
mounted2.cleanup(); assert.equal(mountTarget.children.length, 0);
console.log('Battery explorer: resolver safety, 6 figure pins, hover/focus, titleZh escaping, paper callback, selection, cleanup PASS');
