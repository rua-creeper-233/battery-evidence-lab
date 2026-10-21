import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
const inlineApp = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1].replace(/\n\s*loadData\(\);\s*$/, '\n');

class ClassList {
  constructor() { this.values = new Set(); }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) { const on = force === undefined ? !this.values.has(name) : force; if (on) this.add(name); else this.remove(name); return on; }
}
class Element {
  constructor(id = '') { this.id = id; this.value = ''; this.checked = false; this.files = []; this.innerHTML = ''; this.textContent = ''; this.className = ''; this.classList = new ClassList(); this.listeners = {}; this.disabled = false; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  setAttribute() {}
  removeAttribute() {}
}

const ids = ['ask', 'question', 'answer', 'toolAgent', 'serviceMessage', 'paperList', 'listCount', 'detail', 'modal', 'close', 'filter', 'openUpload', 'closeUpload', 'uploadModal', 'testApi', 'disconnectApi', 'uploadForm', 'apiBase', 'apiToken', 'paperFile', 'submitUpload', 'uploadResult', 'apiStat', 'ragStat', 'paperCount', 'starterStat', 'zoteroStat'];
const nodes = new Map(ids.map(id => [id, new Element(id)]));
const document = {
  querySelector(selector) { return selector.startsWith('#') ? nodes.get(selector.slice(1)) : null; },
  querySelectorAll() { return []; },
  createElement() { return new Element(); },
};
const paper = {id: 'p1', doi: '10.1000/ABC', title: '<Paper & title>', year: 2024, authors: [], journal: 'J'};
const knowledgeCard = {
  id: 'faq_msd_units', kind: 'faq', question: 'MSD <unit> check',
  answer: 'Answer & verify', steps: ['Step <one>'], checks: ['Check "two"'], boundary: 'Boundary > verify',
  sources: [{paper_id: 'p1', doi: paper.doi, locator: 'abstract <x>', note: 'Note & cite'}],
  documentation: [{label: 'Docs <safe>', url: 'https://docs.lammps.org/compute_msd.html', locator: 'manual'}],
};
const knowledge = {cards: [knowledgeCard], notice: 'Knowledge notice'};
const deterministic = {answer_markdown: 'deterministic answer', papers: []};
const fetch = async url => ({ok: true, status: 200, async json() { assert.equal(url, '/api/chat'); return {answer_markdown: 'API answer'}; }});
const context = vm.createContext({
  URL, URLSearchParams, FormData, console, fetch, document,
  window: {
    state: {papers: [paper], staticQa: null, researchKnowledge: knowledge, searchConfig: {}},
    BatteryBrowserAgent: {answer() { return {...deterministic}; }},
    BatteryResearchKnowledge: {lookup() { return knowledge; }},
    BatteryStaticQA: {lookup() { return {cards: []}; }},
  },
  location: {protocol: 'http:', hostname: '127.0.0.1', search: ''},
  localStorage: {getItem() { return ''; }, setItem() {}},
  sessionStorage: {getItem() { return ''; }, setItem() {}},
  navigator: {}, alert() {},
});
vm.runInContext(inlineApp, context);
context.window.state.papers = [paper];
context.window.state.researchKnowledge = knowledge;
nodes.get('question').value = 'MSD units';
await nodes.get('ask').onclick();
const rendered = nodes.get('answer').innerHTML;
assert.ok(rendered.indexOf('API answer') < rendered.indexOf('MSD &lt;unit&gt; check'), 'API-primary answer must precede knowledge');
for (const unsafe of ['<Paper & title>', 'Answer & verify', '<x>', 'Docs <safe>']) assert.equal(rendered.includes(unsafe), false, `unsafe text was not escaped: ${unsafe}`);
for (const safe of ['&lt;Paper &amp; title&gt;', 'Answer &amp; verify', 'abstract &lt;x&gt;', 'Docs &lt;safe&gt;', 'DOI']) assert.match(rendered, new RegExp(safe.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
assert.match(rendered, /Step &lt;one&gt;/);
assert.match(rendered, /Check &quot;two&quot;/);
assert.match(rendered, /Boundary &gt; verify/);
console.log('research knowledge UI ordering and escaping tests passed');
