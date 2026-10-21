import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../static/lab-ui.js', import.meta.url), 'utf8');

async function run({titlePayload = {}, statusPayload = {}, readyState = 'complete', statusOk = true} = {}) {
  const progress = [{textContent: '静态回退'}];
  const listeners = {};
  const document = {
    readyState,
    addEventListener(type, callback) { listeners[type] = callback; },
    querySelectorAll(selector) { return selector === '[data-project-progress]' ? progress : []; },
  };
  const response = (payload, ok = true) => ({ok, async json() { return payload; }});
  const fetch = async (url) => url.includes('paper_titles_zh') ? response(titlePayload) : response(statusPayload, statusOk);
  const window = {};
  vm.runInContext(source, vm.createContext({window, document, fetch, console}));
  await window.LabUI.ready;
  await window.LabUI.progressReady;
  return {window, document, listeners, progress};
}

let t = await run({
  titlePayload: {papers: {p1: {title: 'English <title>', title_zh: '中文 <危险>'}}},
  statusPayload: {as_of: '2026-10-14', papers: 176, dataset_rows: 998},
});
assert.equal(t.window.LabUI.titleZh({id: 'p1', title: 'English <title>'}), '中文 <危险>');
assert.match(t.window.LabUI.paperTitleHtml({id: 'p1', title: 'English <title>'}), /English &lt;title&gt;/);
assert.match(t.window.LabUI.paperTitleHtml({id: 'p1', title: 'English <title>'}), /中文 &lt;危险&gt;/);
assert.doesNotMatch(t.window.LabUI.paperTitleHtml({id: 'p1', title: 'English <title>'}), /<危险>/);
assert.equal(t.progress[0].textContent, '176 篇论文 · 更新于 2026-10-14');

t = await run({titlePayload: {papers: {p1: {title: 'Old English', title_zh: '不应显示'}}}});
assert.equal(t.window.LabUI.titleZh({id: 'p1', title: 'Current English'}), '');
assert.doesNotMatch(t.window.LabUI.paperTitleHtml({id: 'p1', title: 'Current English'}), /不应显示/);
assert.equal(t.window.LabUI.titleZh({id: 'missing', title: 'Fallback'}), '');

t = await run({titlePayload: {papers: {cn: {title: '中文原题', title_zh: '中文原题'}}}});
assert.equal(t.window.LabUI.titleZh({id: 'cn', title: '中文原题'}), '中文原题', 'Chinese title stays searchable');
assert.equal((t.window.LabUI.paperTitleHtml({id: 'cn', title: '中文原题'}).match(/中文原题/g) || []).length, 1, 'Chinese originals must not show an identical subtitle');

t = await run({
  readyState: 'loading',
  titlePayload: {papers: {}},
  statusPayload: {as_of: '2026-10-14', papers: 176, dataset_rows: 998},
});
assert.equal(t.progress[0].textContent, '静态回退', 'status must wait for DOM readiness');
t.listeners.DOMContentLoaded();
assert.equal(t.progress[0].textContent, '176 篇论文 · 更新于 2026-10-14');

t = await run({
  titlePayload: {papers: {}},
  statusPayload: {as_of: 'not-a-date', papers: -1, dataset_rows: 0},
});
assert.equal(t.progress[0].textContent, '静态回退', 'invalid status must preserve static fallback');

t = await run({statusPayload:{as_of:'2026-10-20',papers:211,dataset_rows:998,static_qa:{catalog_papers:211,rows:844}}});
assert.equal(t.progress[0].textContent, '211 篇论文 · 更新于 2026-10-20');
t = await run({statusPayload:{as_of:'2026-10-20',papers:211,dataset_rows:998,static_qa:{catalog_papers:211,rows:844},research_knowledge:{cards:40}}});
assert.equal(t.progress[0].textContent, '211 篇论文 · 更新于 2026-10-20');
t = await run({statusPayload:{as_of:'2026-10-20',papers:211,dataset_rows:998,static_qa:{catalog_papers:211,rows:999}}});
assert.equal(t.progress[0].textContent, '211 篇论文 · 更新于 2026-10-20', 'invalid extra statistics must not appear in the compact progress line');

console.log('Lab UI: bilingual title escaping/fallback, DOM-ready progress, invalid status fallback PASS');
assert.equal(t.window.LabUI.verificationLabel('verified_crossref_2026-10-08'), 'Crossref 已核验');
assert.equal(t.window.LabUI.verificationLabel('verified_crossref_and_publisher'), 'Crossref 与出版社已核验');
assert.equal(t.window.LabUI.verificationLabel('verified_publisher_and_pdf'), '出版社与正文已核验');
assert.equal(t.window.LabUI.verificationLabel('not_checked'), '书目核验状态待补充');
assert.equal(t.window.LabUI.verificationLabel('<img onerror=x>'), '书目核验状态待补充');
assert.equal(t.window.LabUI.paperSummary({role:'面向电池电解液、固态电解质、正极/界面模拟的可复用计算文献。',summary:'基于 Crossref 出版社元数据核验：Title。摘要/正文参数仍需按来源逐项复核。'}), '内容摘录待补充');
assert.equal(t.window.LabUI.paperSummary({role:'扩散机制',summary:'研究了协同离子扩散。'}), '扩散机制 · 研究了协同离子扩散。');
