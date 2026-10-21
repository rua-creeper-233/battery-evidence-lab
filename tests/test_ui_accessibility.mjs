import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const root = new URL('..', import.meta.url);
const read = (name) => fs.readFileSync(new URL(name, root), 'utf8');
const cssFiles = ['static/lab-ui.css', 'static/home.css', 'static/battery_explorer.css', 'static/domestic-papers.css', 'static/tutorials.css'];
const authoredPages = ['static/foundations.html', 'static/ai-battery-applications.html', 'static/future-directions.html'];

function luminance(hex) {
  const rgb = hex.replace('#', '').match(/.{2}/g).map((v) => parseInt(v, 16) / 255);
  const linear = rgb.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}
function contrast(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}

test('assigned source CSS has no sub-12px visible text and SVG text is at least 12px', () => {
  for (const file of cssFiles) {
    const source = read(file);
    for (const match of source.matchAll(/font-size\s*:\s*([0-9.]+)px/gi)) {
      assert.ok(Number(match[1]) >= 12, `${file} contains ${match[1]}px text`);
    }
    for (const match of source.matchAll(/font\s*:\s*[^;{}]*?\b([0-9.]+)px\b/gi)) {
      assert.ok(Number(match[1]) >= 12, `${file} contains ${match[1]}px font shorthand`);
    }
  }
  const explorer = read('static/battery_explorer.css');
  assert.match(explorer, /\.battery-explorer__svg text[^}]*font-size:\s*12px/);
});

test('muted text meets AA contrast on paper and mint surfaces', () => {
  const sources = [read('static/lab-ui.css'), ...authoredPages.map(read)];
  const colors = sources.flatMap((source) => [...source.matchAll(/--muted\s*:\s*(#[0-9a-f]{6})/gi)].map((m) => m[1]));
  assert.ok(colors.length >= 4, 'expected shared and authored muted tokens');
  for (const color of new Set(colors)) {
    assert.ok(contrast(color, '#fafbf8') >= 4.5, `${color} fails paper contrast`);
    assert.ok(contrast(color, '#edf5ef') >= 4.5, `${color} fails mint contrast`);
  }
});

test('authored labels are translated and tutorial steps use a group, not an empty landmark', () => {
  for (const page of authoredPages) {
    const source = read(page);
    assert.doesNotMatch(source, /<span class="num">[^<]*(?:BOOK|PAPER)\b/);
  }
  const tutorial = read('static/tutorials.js');
  assert.match(tutorial, /<div class="tutorial-nav" role="group" aria-label="教程步骤">/);
  assert.doesNotMatch(tutorial, /<nav class="tutorial-nav"/);
});

test('nav overflow cue updates at start, end, resize, and scroll without hiding controls', () => {
  const source = read('static/nav-overflow.js');
  const listeners = {};
  const rows = [];
  const makeRow = () => {
    const row = { scrollWidth: 300, clientWidth: 100, scrollLeft: 0, dataset: {}, listeners: {}, classList: {
      values: new Set(), toggle(name, enabled) { if (enabled) this.values.add(name); else this.values.delete(name); }, add(name) { this.values.add(name); }, remove(name) { this.values.delete(name); },
    }, addEventListener(name, fn) { this.listeners[name] = fn; }, };
    rows.push(row); return row;
  };
  const window = { addEventListener(name, fn) { listeners[name] = fn; } };
  const document = { readyState: 'complete', addEventListener() {}, querySelectorAll() { return rows; } };
  const context = { document, window, ResizeObserver: undefined, MutationObserver: undefined };
  vm.runInNewContext(source, context);
  const row = makeRow();
  context.document.querySelectorAll = () => [row];
  vm.runInNewContext(source, context);
  assert.ok(row.classList.values.has('overflow-right'));
  assert.ok(!row.classList.values.has('overflow-left'));
  row.scrollLeft = 200; row.listeners.scroll();
  assert.ok(row.classList.values.has('overflow-left'));
  assert.ok(!row.classList.values.has('overflow-right'));
  row.scrollWidth = 100; listeners.resize();
  assert.ok(!row.classList.values.has('overflow-left'));
  assert.ok(!row.classList.values.has('overflow-right'));
  row.scrollWidth = 300; listeners.resize(); row.listeners.focusin();
  assert.ok(row.classList.values.has('overflow-focus'));
  row.listeners.focusout();
  assert.ok(!row.classList.values.has('overflow-focus'));
  assert.equal(source.includes('display: none'), false, 'script must not hide overflow controls');
});
