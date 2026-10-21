import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { lookup } = require('../static/static_qa.js');
const data = JSON.parse(fs.readFileSync(new URL('../data/static_qa.json', import.meta.url), 'utf8'));
const p = data.entries[0];
const paper = [{ id: p.paper_id, doi: p.doi, title: p.title }];
let out = lookup('方法 software', paper, data);
assert.equal(out.kind, 'static_metadata_extension');
assert.equal(out.intent, 'methods');
assert.equal(out.cards.length, 1);
assert.equal(out.cards[0].primary.intent, 'methods');
assert.equal(out.cards[0].related.length, 3);
assert.equal(out.cards[0].evidence_level, 'curated_metadata');
assert.deepEqual(lookup('方法', [{ ...paper[0], doi: '10.9999/wrong' }], data).cards, []);
assert.deepEqual(lookup('', paper, data).cards, []);
assert.deepEqual(lookup('方法', paper, { ...data, entries: [] }).cards, []);
const attacked = structuredClone(data);
attacked.entries[0].qas[0].source_urls[0] = 'http://evil.test/not-a-doi';
assert.deepEqual(lookup('方法', paper, attacked).cards, []);
const dup = lookup('中文 入门', [paper[0], paper[0]], data);
assert.ok(dup.cards.length <= 1);
const small = structuredClone(data);
small.entries = small.entries.slice(0, 2); small.catalog_count = 2; small.qa_count = 8;
const reversed = small.entries.slice().reverse().map(e => ({id:e.paper_id,doi:e.doi,title:e.title}));
const limits = lookup('方法有哪些局限和限制', reversed, small);
assert.equal(limits.intent, 'limitations');
assert.deepEqual(limits.cards.map(c => c.paper_id), reversed.map(p => p.id));
assert.deepEqual(limits.coverage, {papers:2,qa:8});
assert.deepEqual(lookup('unmatched nonsense', [], small).cards, []);
for (const tamper of [
  d => { d.entries[0].private_key = 'not_public'; },
  d => { d.entries[0].qas[0].source_fields = ['local_pdf']; },
  d => { d.entries[0].qas[1] = d.entries[0].qas[0]; },
  d => { d.entries[1].doi = d.entries[0].doi; },
  d => { d.private_key = 'not_public'; },
]) {
  const invalid = structuredClone(small); tamper(invalid);
  assert.deepEqual(lookup('方法', reversed, invalid).cards, []);
}
console.log('static QA lookup tests passed');
