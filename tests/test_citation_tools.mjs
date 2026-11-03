import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const tools = require('../static/citation-tools.js');

const paper = {
  id: 'p-1',
  title: 'A {safe} battery study',
  authors: ['Ada Lovelace', 'Grace Hopper'],
  year: 2024,
  journal: 'Journal of Testing',
  doi: 'https://doi.org/10.1234/example'
};

assert.equal(tools.doiText(paper), '10.1234/example');
const bib = tools.bibtex(paper);
assert.match(bib, /^@article\{adalovelace2024p1,/);
assert.match(bib, /author = \{Ada Lovelace and Grace Hopper\}/);
assert.match(bib, /title = \{\{A \\{safe\\\} battery study\}\}/);
assert.match(bib, /journal = \{Journal of Testing\}/);
assert.match(bib, /doi = \{10\.1234\/example\}/);
assert.match(tools.actionsHtml(paper), /data-citation-action="doi"/);
assert.match(tools.actionsHtml({ id: 'missing' }), /data-citation-action="bibtex"/);

const paperRow = { id: 'api-paper', title: 'API paper' };
let requests = [];
const loader = tools.createCatalogLoader({
  fetchImpl: async url => {
    requests.push(url);
    if (url === './data/papers.json') return { ok: false, json: async () => ({}) };
    return { ok: true, json: async () => ({ papers: [paperRow] }) };
  }
});
assert.deepEqual(await loader(), [paperRow]);
assert.deepEqual(requests, ['./data/papers.json', '/api/papers']);
assert.deepEqual(await loader(), [paperRow]);
assert.equal(requests.length, 2, 'successful catalog is reused for later copy actions');

let calls = 0;
const retryLoader = tools.createCatalogLoader({
  fetchImpl: async () => ({ ok: true, json: async () => { calls += 1; return calls <= 2 ? { malformed: true } : [paperRow]; } })
});
assert.deepEqual(await retryLoader(), []);
assert.deepEqual(await retryLoader(), [paperRow]);
assert.equal(calls, 3);

const host = { state: { papers: [] } };
const stateLoader = tools.createCatalogLoader({ host, fetchImpl: async () => ({ ok: false }) });
const pending = stateLoader();
host.state.papers = [paperRow];
assert.deepEqual(await stateLoader(), [paperRow]);
assert.deepEqual(await pending, [paperRow]);

const lateHost = { state: { papers: [] } };
const lateLoader = tools.createCatalogLoader({ host: lateHost, fetchImpl: async () => {
  lateHost.state.papers = [paperRow];
  return { ok: true, json: async () => [{ id: 'stale', title: 'Stale catalog' }] };
} });
assert.deepEqual(await lateLoader(), [paperRow], 'live catalog wins over an in-flight stale response');

console.log('citation tools ok');

const source = fs.readFileSync(new URL('../static/citation-tools.js', import.meta.url), 'utf8');
function runtime({ clipboardRejects = false, legacyCopy = false } = {}) {
  const events = new Map(), nodes = [], copied = [];
  function node(tag) {
    const value = {
      tagName: tag.toUpperCase(), dataset: {}, style: {}, children: [], hidden: false,
      setAttribute(key, val) { this[key] = val; },
      addEventListener(name, fn) { this[name] = fn; },
      focus() { this.focused = true; }, select() { this.selected = true; }, remove() { this.removed = true; },
      querySelector(selector) { return this.children.find(child => selector === 'textarea' ? child.tagName === 'TEXTAREA' : child.dataset.citationClose !== undefined); },
      set innerHTML(_) { const close = node('button'); close.dataset.citationClose = ''; this.children = [close, node('textarea')]; },
    };
    return value;
  }
  const doc = {
    readyState: 'complete', documentElement: { dataset: {} },
    body: { appendChild(n) { nodes.push(n); } },
    addEventListener(name, fn, capture) { events.set(name, { fn, capture }); },
    createElement: node,
    querySelector(selector) { return nodes.find(n => selector === '[data-citation-status]' ? n.dataset.citationStatus !== undefined : n.dataset.citationManual !== undefined); },
    execCommand() { return legacyCopy; },
  };
  const context = vm.createContext({
    document: doc, state: { papers: [paper] },
    navigator: { clipboard: { async writeText(value) { if (clipboardRejects) throw Error('blocked'); copied.push(value); } } },
    setTimeout(fn, delay) { if (!delay) fn(); return 1; }, clearTimeout() {},
  });
  vm.runInContext(source, context);
  const click = async action => {
    const button = node('button'); button.dataset = { paperId: 'p-1', citationAction: action };
    const event = { target: { closest: () => button }, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
    events.get('click').fn(event);
    for (let i = 0; i < 8; i++) await Promise.resolve();
    return { button, event };
  };
  return { doc, events, nodes, context, copied, click };
}

test('late-loaded runtime installs itself and copies dynamic card metadata without opening its parent', async () => {
  const env = runtime();
  assert.equal(env.events.get('click').capture, true);
  const result = await env.click('doi');
  assert.equal(result.event.prevented, true);
  assert.equal(result.event.stopped, true);
  assert.equal(env.copied[0], '10.1234/example');
  assert.match(env.doc.querySelector('[data-citation-status]').textContent, /DOI 已复制/);
  await env.click('bibtex');
  assert.equal(env.copied[1], bib);
});

test('denied clipboard offers selected manual text and restores focus on Escape', async () => {
  const env = runtime({ clipboardRejects: true });
  const { button } = await env.click('bibtex');
  const panel = env.doc.querySelector('[data-citation-manual]');
  assert.ok(panel);
  assert.equal(panel.hidden, false);
  assert.equal(panel.querySelector('textarea').value, bib);
  assert.equal(panel.querySelector('textarea').selected, true);
  assert.match(env.doc.querySelector('[data-citation-status]').textContent, /无法写入剪贴板/);
  panel.keydown({ key: 'Escape', preventDefault() {} });
  assert.equal(panel.hidden, true);
  assert.equal(button.focused, true);
});
