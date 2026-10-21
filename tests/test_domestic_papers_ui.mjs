import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const code = fs.readFileSync(new URL('../static/domestic-papers.js', import.meta.url), 'utf8');

function run() {
  const events = {};
  const controls = new Map();
  const cards = [
    {id: 'zh-baseline', dataset: {category: 'chinese_original', topic: 'reviews', stage: 'baseline', frontiers: '', search: '中文原文 电池综述 中文期刊 中国内地 2024 baseline'}, hidden: false},
    {id: 'zh-intermediate', dataset: {category: 'chinese_original', topic: 'reviews', stage: 'intermediate', frontiers: 'f1', search: '中文原文 电池扩散 中文期刊 中国内地 2023 intermediate 方向一'}, hidden: false},
    {id: 'zh-frontier', dataset: {category: 'chinese_original', topic: 'reviews', stage: 'frontier', frontiers: 'f1', search: '中文原文 电池前沿 中文期刊 中国内地 2022 frontier 方向一'}, hidden: false},
    {id: 'en', dataset: {category: 'team_english', topic: 'mlip', stage: '', frontiers: '', search: 'English model paper team laboratory 中国香港 2025 10.1000/en'}, hidden: false},
  ];
  const stages = [];
  const frontierLink = {dataset: {targetCard: 'zh-intermediate'}, hidden: false, closest: () => frontierLink};
  const frontier = {dataset: {search: '方向一'}, hidden: false, open: false, querySelectorAll: (sel) => sel === '.domestic-frontier-link' ? [frontierLink] : []};
  const stageFor = (stage) => {
    const node = {dataset: {stage, search: stage}, hidden: false, open: stage === 'baseline', tagName: 'DETAILS', parentElement: null};
    node.querySelector = (sel) => {
      if (sel === '.domestic-card:not([hidden])') return cards.find(card => card.dataset.stage === stage && !card.hidden) || null;
      if (sel === '.domestic-frontier-group:not([hidden])') return stage === 'frontier' && !frontier.hidden ? frontier : null;
      return null;
    };
    stages.push(node);
    return node;
  };
  stageFor('baseline'); stageFor('beginner'); stageFor('intermediate'); stageFor('frontier');
  frontier.parentElement = stages[3];
  cards.forEach(card => { card.parentElement = stages.find(stage => stage.dataset.stage === card.dataset.stage) || null; });
  const groups = [
    {dataset: {group: 'chinese_original'}, hidden: false, querySelector: (sel) => sel === '.domestic-card:not([hidden])' ? cards.find(card => card.dataset.category === 'chinese_original' && !card.hidden) || null : null},
    {dataset: {group: 'team_english'}, hidden: false, querySelector: (sel) => sel === '.domestic-card:not([hidden])' ? cards.find(card => card.dataset.category === 'team_english' && !card.hidden) || null : null},
  ];
  const make = (id, value = '') => {
    const el = {id, value, textContent: '', hidden: false, addEventListener(type, fn) { events[`${id}:${type}`] = fn; }};
    controls.set(`#${id}`, el);
    return el;
  };
  make('domestic-search'); make('domestic-category', 'all'); make('domestic-topic', 'all');
  make('domestic-count'); make('domestic-empty'); make('domestic-reset');
  const document = {
    querySelector: (sel) => {
      if (controls.has(sel)) return controls.get(sel);
      if (sel.startsWith('.domestic-stage:not')) return stages.find(stage => !stage.hidden);
      if (sel.startsWith('.domestic-frontier-group:not')) return !frontier.hidden ? frontier : null;
      if (sel.includes('.domestic-stage:not') || sel.includes('.domestic-frontier-group:not')) return stages.find(stage => !stage.hidden) || (!frontier.hidden ? frontier : null);
      return undefined;
    },
    querySelectorAll: (sel) => sel === '.domestic-card' ? cards : sel === '.domestic-group' ? groups : sel === '.domestic-stage' ? stages : sel === '.domestic-frontier-group' ? [frontier] : [],
    getElementById: (id) => cards.find(card => card.id === id) || null,
    addEventListener: (type, fn) => { events[`document:${type}`] = fn; },
  };
  vm.runInNewContext(code, {document});
  return {cards, groups, stages, frontier, frontierLink, controls, events};
}

const t = run();
assert.match(t.controls.get('#domestic-count').textContent, /显示 4 \/ 4 篇/);
assert.equal(t.stages[0].open, true, 'baseline is open by default');
assert.equal(t.stages[1].open, false, 'non-baseline stages are collapsed by default');

t.controls.get('#domestic-category').value = 'chinese_original';
t.events['domestic-category:input']();
assert.deepEqual(t.cards.filter(card => !card.hidden).map(card => card.id), ['zh-baseline', 'zh-intermediate', 'zh-frontier']);
assert.equal(t.groups[1].hidden, true, 'English group hides when category has no visible cards');

t.controls.get('#domestic-category').value = 'all';
t.controls.get('#domestic-topic').value = 'mlip';
t.events['domestic-topic:input']();
assert.deepEqual(t.cards.filter(card => !card.hidden).map(card => card.id), ['en']);
t.controls.get('#domestic-search').value = 'baseline';
t.events['domestic-search:input']();
assert.equal(t.cards.filter(card => !card.hidden).length, 0, 'baseline search does not leak Chinese cards through English category filter');
assert.equal(t.controls.get('#domestic-empty').hidden, false, 'no-results message is shown for incompatible filters');

t.events['domestic-reset:click']();
t.controls.get('#domestic-search').value = 'laboratory';
t.events['domestic-search:input']();
assert.deepEqual(t.cards.filter(card => !card.hidden).map(card => card.id), ['en'], 'unit text is searchable');
t.controls.get('#domestic-search').value = '2025';
t.events['domestic-search:input']();
assert.deepEqual(t.cards.filter(card => !card.hidden).map(card => card.id), ['en'], 'year text is searchable');
t.controls.get('#domestic-search').value = '10.1000/en';
t.events['domestic-search:input']();
assert.deepEqual(t.cards.filter(card => !card.hidden).map(card => card.id), ['en'], 'DOI text is searchable');

t.controls.get('#domestic-search').value = 'does-not-exist';
t.events['domestic-search:input']();
assert.equal(t.cards.filter(card => !card.hidden).length, 0);
assert.equal(t.controls.get('#domestic-empty').hidden, false, 'no-results message is shown');
assert.equal(t.groups.every(group => group.hidden), true, 'both groups hide on no results');

t.events['domestic-reset:click']();
assert.equal(t.controls.get('#domestic-search').value, '');
assert.equal(t.controls.get('#domestic-category').value, 'all');
assert.equal(t.controls.get('#domestic-topic').value, 'all');
assert.equal(t.cards.filter(card => !card.hidden).length, 4, 'reset restores all cards');
assert.equal(t.controls.get('#domestic-empty').hidden, true);
assert.equal(t.stages[0].open, true, 'reset restores baseline open state');
assert.equal(t.stages[1].open, false, 'reset restores collapsed non-baseline state');

t.controls.get('#domestic-search').value = '方向一';
t.events['domestic-search:input']();
assert.equal(t.frontier.open, true, 'matching frontier cross-reference group opens on search');
assert.equal(t.frontier.hidden, false, 'matching frontier group remains visible');
assert.equal(t.frontierLink.hidden, false, 'matching individual frontier link remains visible');
t.events['document:click']({target: {closest: () => t.frontierLink}});
assert.equal(t.stages[2].open, true, 'clicking cross-reference opens the target intermediate stage');

t.controls.get('#domestic-search').value = '';
t.controls.get('#domestic-category').value = 'team_english';
t.events['domestic-category:input']();
assert.equal(t.frontier.hidden, true, 'frontier crosslink group hides when its cards are filtered out');
assert.equal(t.frontierLink.hidden, true, 'individual frontier link hides when target is filtered out');

assert.doesNotMatch(code, /innerHTML|createElement|document\.write/, 'page behavior must filter prerendered cards');
assert.match(code, /domestic-stage/);
assert.match(code, /domestic-frontier-group/);
console.log('Domestic papers UI: category/topic/unit/year/DOI search, reset, empty state, groups, cross-stage links, static cards PASS');
