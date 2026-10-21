import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';

const homeCode = fs.readFileSync(new URL('../static/home.js', import.meta.url), 'utf8');

class ClassList {
  constructor() { this.values = new Set(); }
  toggle(name, force) { const on = force === undefined ? !this.values.has(name) : force; if (on) this.values.add(name); else this.values.delete(name); return on; }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  contains(name) { return this.values.has(name); }
}

class Element {
  constructor({id = '', dataset = {}} = {}) {
    this.id = id; this.dataset = dataset; this.classList = new ClassList();
    this.attributes = {}; this.listeners = {}; this.children = []; this.hidden = false;
    this.disabled = false; this._text = ''; this.innerHTML = ''; this.value = '';
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  dispatch(name, event = {}) { for (const fn of this.listeners[name] || []) fn(event); }
  appendChild(child) { this.children.push(child); return child; }
  focus() { this.focused = true; }
  querySelector(selector) {
    if (selector === '.robot-button') return this.robotButton;
    if (selector === '.robot-bubble') return this.robotBubble;
    if (selector === '.robot-actions') return this.robotActions;
    if (selector === '[data-robot-next]') return this.robotNext;
    if (selector === '[data-robot-close]') return this.robotClose;
    return null;
  }
}

function makeHomeContext(hash = '#unknown', paperList = []) {
  const panels = ['research-question', 'library', 'tutorials', 'future-directions'].map(data => new Element({dataset: {homePanel: data}}));
  const tabs = panels.slice(0, 3).map(panel => new Element({dataset: {homeTab: panel.dataset.homePanel}}));
  const body = new Element();
  const document = {
    body,
    querySelector() { return null; },
    querySelectorAll(selector) { return selector === '[data-home-panel]' ? panels : selector === '[data-home-tab]' ? tabs : []; },
    createElement(tag) {
      const e = new Element(); e.tagName = tag;
      if (tag === 'span') Object.defineProperty(e, 'textContent', {set(value) { this.innerHTML = String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;'); }, get() { return this._text || ''; }});
      return e;
    },
  };
  const location = {hash};
  const history = {pushes: [], pushState(_a, _b, next) { this.pushes.push(next); location.hash = next; }};
  const window = {state: {papers: paperList}, setInterval() { return 1; }, clearInterval() {}, addEventListener(name, fn) { this[`on${name}`] = fn; }};
  const context = vm.createContext({document, window, location, history, console, setInterval() { return 1; }, clearInterval() {}});
  // home.js builds these descendants through robot.innerHTML; provide the tiny DOM
  // surface it consumes while preserving the production event flow.
  const originalAppend = body.appendChild.bind(body);
  body.appendChild = child => {
    if (child.className === 'robot-widget') {
      child.robotButton = new Element(); child.robotBubble = new Element(); child.robotActions = new Element();
      child.robotNext = new Element(); child.robotClose = new Element();
      child.querySelector = Element.prototype.querySelector;
    }
    return originalAppend(child);
  };
  return {context, panels, tabs, body, location, history, window};
}

// Navigation defaults to the canonical panel, marks the active tab, and supports
// both click navigation and browser back/forward hash changes.
{
  const h = makeHomeContext('#not-a-panel');
  vm.runInContext(homeCode, h.context);
  assert.equal(h.panels[0].classList.contains('is-active'), true);
  assert.equal(h.tabs[0].attributes['aria-selected'], 'true');
  assert.equal(h.panels[1].hidden, true);
  h.tabs[1].dispatch('click', {preventDefault() {}});
  assert.equal(h.location.hash, '#library');
  assert.equal(h.panels[1].classList.contains('is-active'), true);
  assert.deepEqual(h.history.pushes, ['#library']);
  h.location.hash = '#tutorials'; h.window.onhashchange();
  assert.equal(h.panels[2].classList.contains('is-active'), true);
  assert.equal(h.tabs[1].attributes['aria-selected'], 'false');
  h.location.hash = '#library'; h.window.onpopstate();
  assert.equal(h.panels[1].hidden, false);
  h.tabs[1].dispatch('keydown', {key: 'ArrowRight', preventDefault() {}});
  assert.equal(h.tabs[2].focused, true);
  assert.equal(h.location.hash, '#tutorials');
  h.tabs[2].dispatch('keydown', {key: 'Home', preventDefault() {}});
  assert.equal(h.location.hash, '#research-question');
  h.tabs[0].dispatch('keydown', {key: 'End', preventDefault() {}});
  assert.equal(h.location.hash, '#tutorials');
}

// Robot first click previews a random paper, second click opens that paper;
// empty and singleton catalogs remain safe and do not throw.
{
  const shown = [];
  const h = makeHomeContext('', [{id: 'a', title: '<unsafe>', year: 2024}, {id: 'b', title: 'Second'}]);
  h.window.showPaper = id => shown.push(id);
  vm.runInContext(homeCode, h.context);
  const robot = h.body.children.find(x => x.className === 'robot-widget');
  robot.robotButton.dispatch('click');
  assert.equal(robot.robotBubble.hidden, false);
  assert.match(robot.robotBubble.innerHTML, /&lt;unsafe&gt;|Second/);
  robot.robotButton.dispatch('click');
  assert.equal(shown.length, 1);
  robot.robotNext.dispatch('click');
  assert.equal(robot.robotBubble.hidden, false);

  const empty = makeHomeContext('', []); vm.runInContext(homeCode, empty.context);
  const emptyRobot = empty.body.children.find(x => x.className === 'robot-widget');
  emptyRobot.robotButton.dispatch('click');
  assert.match(emptyRobot.robotBubble.textContent, /尚未加载/);
  const singleton = makeHomeContext('', [{id: 'only', title: 'Only'}]); vm.runInContext(homeCode, singleton.context);
  const singletonRobot = singleton.body.children.find(x => x.className === 'robot-widget');
  singletonRobot.robotButton.dispatch('click'); singletonRobot.robotNext.dispatch('click');
  assert.match(singletonRobot.robotBubble.textContent, /暂无可重复推荐/);
}

// Static extension is fail-closed and escapes rendered metadata. This complements
// the dataset-level tests with the exact extension boundary consumed by home UI.
{
  const require = createRequire(import.meta.url);
  const {lookup} = require('../static/static_qa.js');
  const data = JSON.parse(fs.readFileSync(new URL('../data/static_qa.json', import.meta.url), 'utf8'));
  const entry = data.entries[0];
  const paper = {id: entry.paper_id, doi: entry.doi, title: entry.title};
  const extension = lookup('方法 software', [paper], data);
  assert.equal(extension.cards.length, 1);
  assert.equal(extension.cards[0].primary.intent, 'methods');
  assert.deepEqual(lookup('方法', [paper], {...data, static_extension: false}).cards, []);
  const malicious = {...paper, title: '<img src=x onerror=alert(1)>'};
  assert.equal(lookup('方法', [malicious], data).cards.length, 0);
}

console.log('home navigation, robot safety, and static extension boundary tests passed');

// Execute the real inline search app in a small DOM/VM harness.  This exercises
// ask()'s service fallback and API-primary branches instead of only inspecting
// the pure lookup module.
{
  const html = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
  const inlineApp = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1].replace(/\n\s*loadData\(\);\s*$/, '\n');
  const nodeMap = new Map();
  const ids = ['ask', 'question', 'answer', 'toolAgent', 'serviceMessage', 'paperList', 'listCount', 'detail', 'modal', 'close', 'filter', 'openUpload', 'closeUpload', 'uploadModal', 'testApi', 'uploadForm', 'apiBase', 'apiToken', 'paperFile', 'submitUpload', 'uploadResult', 'apiStat', 'ragStat', 'paperCount', 'starterStat', 'zoteroStat'];
  const nodeFor = id => {
    if (!nodeMap.has(id)) {
      const n = new Element({id}); n.checked = false; n.files = []; n.classList = new ClassList();
      nodeMap.set(id, n);
    }
    return nodeMap.get(id);
  };
  const document = {
    querySelector(selector) { return selector.startsWith('#') ? nodeFor(selector.slice(1)) : null; },
    querySelectorAll(selector) { return selector === '.chip' || selector === '.filter-chip' || selector === '.paper' ? [] : ids.map(nodeFor); },
    createElement(tag) { const n = new Element(); n.tagName = tag; return n; },
  };
  const dataset = JSON.parse(fs.readFileSync(new URL('../data/static_qa.json', import.meta.url), 'utf8'));
  const entry = dataset.entries[0];
  const paper = {id: entry.paper_id, doi: entry.doi, title: entry.title, year: 2024, journal: 'J', role: 'role', summary: 'summary', authors: []};
  const deterministic = question => ({answer_markdown: `deterministic ${question}`, papers: question.includes('unknown') ? [] : [paper]});
  const extension = {label: '静态知识延伸', notice: '关键词/字符匹配与元数据导读，非模型生成', cards: [{paper_id: paper.id, title: paper.title, primary: {question: 'Q', answer: 'A', source_urls: [`https://doi.org/${paper.doi}`]}, related: []}]};
  async function exercise(kind, payload, question = '方法 software', keyEvent = null) {
    const calls = [];
    const fetch = async (url) => {
      calls.push(url);
      if (kind.includes('offline')) return {ok: false, status: 503, async json() { return {error: 'offline'}; }};
      return {ok: true, status: 200, async json() { return payload; }};
    };
    const window = {LabUI: {paperTitleHtml(p) { return `<span>${p.title}</span>`; }}, BatteryBrowserAgent: {answer: deterministic}, BatteryStaticQA: {lookup(q, papers, got) { assert.equal(got, dataset); return papers.length ? extension : {...extension, cards: []}; }}};
    const context = vm.createContext({URL, URLSearchParams, FormData, console, fetch, document, window, location: {protocol: 'http:', hostname: '127.0.0.1', search: ''}, localStorage: {getItem() { return ''; }, setItem() {}}, sessionStorage: {getItem() { return ''; }, setItem() {}}, navigator: {}, alert() {}});
    nodeFor('question').listeners = {};
    vm.runInContext(inlineApp, context);
    context.window.state.papers = [paper]; context.window.state.staticQa = dataset; context.window.state.searchConfig = {};
    nodeFor('question').value = question; nodeFor('toolAgent').checked = kind.includes('tool');
    nodeFor('answer').innerHTML = '';
    if (keyEvent) {
      for (const listener of nodeFor('question').listeners.keydown || []) await listener({preventDefault() {}, ...keyEvent});
    } else await nodeFor('ask').onclick();
    return {html: nodeFor('answer').innerHTML, calls};
  }
  const offline = await exercise('offline', {});
  assert.ok(offline.calls.includes('/api/chat'));
  assert.match(offline.html, /静态知识延伸/);
  assert.match(offline.html, /deterministic 方法 software/);

  const toolOffline = await exercise('tool-offline', {});
  assert.ok(toolOffline.calls.includes('/api/agent'));
  assert.match(toolOffline.html, /静态知识延伸/);

  const tool = await exercise('tool', {answer_markdown: 'tool answer', papers: [], agent: {mode: 'tool_agent', notice: 'tool checked'}});
  assert.match(tool.html, /tool checked/);
  assert.match(tool.html, /静态知识延伸/);

  const rag = await exercise('api', {answer_markdown: 'API answer', papers: [], rag: {used: true, model: 'test-model'}});
  assert.ok(rag.html.indexOf('RAG 已启用') < rag.html.indexOf('静态知识延伸'));
  const apiNoRag = await exercise('api', {answer_markdown: 'API answer', papers: []});
  assert.match(apiNoRag.html, /规则检索 · 人工整理的知识与目录导读/);

  const malformed = await exercise('api', {answer_markdown: 'bad payload', papers: {} });
  assert.match(malformed.html, /静态检索与知识延伸/);
  const unknown = await exercise('offline', {}, 'unknown question');
  assert.doesNotMatch(unknown.html, /static-extension-card/);
  for (const modifiers of [{}, {ctrlKey:true}, {metaKey:true}]) {
    const submission = await exercise('offline', {}, '方法', {key:'Enter', ...modifiers});
    assert.equal(submission.calls.filter(url => url === '/api/chat').length, 1, 'Enter submits exactly once');
  }
  for (const modifiers of [{shiftKey:true}, {isComposing:true}]) {
    const submission = await exercise('offline', {}, '方法', {key:'Enter', ...modifiers});
    assert.equal(submission.calls.length, 0, 'newline/IME composition does not submit');
  }
}

console.log('inline ask fallback/API-primary tests passed');
