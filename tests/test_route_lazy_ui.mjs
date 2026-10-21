import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const code = fs.readFileSync(new URL('../static/learning-route.js', import.meta.url), 'utf8');

class Node {
  constructor({tag = 'div', id = '', classes = [], dataset = {}, text = ''} = {}) {
    this.tagName = tag.toUpperCase(); this.id = id; this.className = classes.join(' ');
    this.dataset = dataset; this.textContent = text; this.children = []; this.parentElement = null;
    this.hidden = false; this.open = false; this.listeners = {};
  }
  append(child) { child.parentElement = this; this.children.push(child); return child; }
  matches(selector) {
    if (selector === 'details') return this.tagName === 'DETAILS';
    if (selector === 'template.paper-template') return this.tagName === 'TEMPLATE' && this.className.includes('paper-template');
    if (selector === 'details[hidden]') return this.tagName === 'DETAILS' && this.hidden;
    if (selector.includes('.paper-card')) return this.className.includes('paper-card');
    if (selector.includes('.stage-card')) return this.className.includes('stage-card');
    if (selector.includes('.frontier-card')) return this.className.includes('frontier-card');
    if (selector.includes('.reference-group')) return this.className.includes('reference-group');
    return false;
  }
  closest(selector) {
    let node = this;
    while (node) { if (node.matches(selector)) return node; node = node.parentElement; }
    return null;
  }
  querySelectorAll(selector) {
    const found = [];
    const visit = (node) => { for (const child of node.children) { if (child.matches(selector)) found.push(child); visit(child); } };
    visit(this); return found;
  }
  cloneNode() {
    const copy = new Node({tag: this.tagName.toLowerCase(), id: this.id, classes: this.className.split(' ').filter(Boolean), dataset: {...this.dataset}, text: this.textContent});
    copy.parentElement = this.parentElement; return copy;
  }
  replaceWith(node) { const siblings = this.parentElement.children; siblings[siblings.indexOf(this)] = node; node.parentElement = this.parentElement; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  focus() {}
  scrollIntoView() { this.scrolled = true; }
}

function template(id, search) {
  const t = new Node({tag: 'template', classes: ['paper-template'], dataset: {paperId: id, search}});
  const article = new Node({tag: 'article', id: `paper-${id}`, classes: ['paper-card'], dataset: {paperId: id}, text: id});
  t.content = {firstElementChild: article}; t.textContent = search; return t;
}

function fixture(hash = '', query = '') {
  const root = new Node();
  const baseline = root.append(new Node({tag: 'details', id: 'stage-baseline', classes: ['stage-card'], dataset: {stage: 'baseline'}})); baseline.open = true;
  const baseCitation = baseline.append(new Node({classes: ['citations']})); baseCitation.append(template('base', 'base method'));
  const refs = baseline.append(new Node({tag: 'details', id: 'reference-group-r', classes: ['reference-group']})); refs.append(template('ref', 'reference method'));
  const frontierStage = root.append(new Node({tag: 'details', id: 'stage-frontier', classes: ['stage-card'], dataset: {stage: 'frontier'}}));
  const frontier = frontierStage.append(new Node({tag: 'details', id: 'frontier-f', classes: ['frontier-card'], dataset: {frontier: 'f'}})); frontier.append(template('frontier', 'frontier method'));
  const controls = new Map();
  const control = (id, value = '') => { const node = new Node({id}); node.value = value; controls.set(`#${id}`, node); return node; };
  control('route-search', query); control('stage-filter', 'all'); control('route-count'); control('route-empty'); control('expand-visible'); control('collapse-visible');
  const document = {
    querySelector: (selector) => controls.get(selector) ?? null,
    querySelectorAll: (selector) => {
      if (selector === '.stage-card, .frontier-card') return [baseline, frontierStage, frontier];
      if (selector.includes('details.stage-card')) return [baseline, frontierStage, refs];
      return root.querySelectorAll(selector);
    },
    getElementById: (id) => [baseline, refs, frontierStage, frontier, ...root.querySelectorAll('.paper-card')].find((node) => node.id === id) ?? null,
  };
  const location = {hash}; const window = {addEventListener() {}};
  vm.runInContext(code, vm.createContext({document, window, location, console, decodeURIComponent}));
  return {root, baseline, refs, frontierStage, frontier, controls};
}

let t = fixture();
assert.equal(baseCitationTemplates(t.baseline), 0, 'open baseline mounts its direct card');
assert.equal(t.refs.querySelectorAll('template.paper-template').length, 1, 'closed reference group remains unmounted');
assert.equal(t.frontier.querySelectorAll('template.paper-template').length, 1, 'closed frontier remains unmounted');
assert.match(t.controls.get('#route-count').textContent, /论文 3\/3/, 'empty query counts mounted and unmounted IDs');
t.refs.open = true; t.refs.listeners.toggle();
assert.equal(t.refs.querySelectorAll('template.paper-template').length, 0, 'opening reference group mounts once');

t = fixture('', 'frontier method');
assert.equal(t.frontier.querySelectorAll('.paper-card').length, 1, 'search mounts an unmounted frontier card');
assert.match(t.controls.get('#route-count').textContent, /论文 1\/3/, 'search count uses matching template metadata');

t = fixture('#paper-frontier');
assert.equal(t.frontierStage.open, true, 'paper hash opens outer stage');
assert.equal(t.frontier.open, true, 'paper hash opens frontier parent');
assert.equal(t.frontier.querySelectorAll('.paper-card').length, 1, 'paper hash materializes target');
console.log('Lazy route UI: template hydration, closed sections, metadata search/counts, and deep hash PASS');

function baseCitationTemplates(stage) {
  return stage.querySelectorAll('template.paper-template').filter((node) => !node.closest('.reference-group')).length;
}
