import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { lookup } = require('../static/research_knowledge.js');
const papers = [{id:'p1', doi:'10.1000/ABC', title:'Foundation paper'}, {id:'p2', doi:'10.1000/DEF', title:'Workflow paper'}];
const source = (paper_id, doi) => ({paper_id, doi, locator:'abstract', note:'evidence'});
const mk = (id, kind, question, aliases, all_of, s) => ({id, kind, question, aliases, all_of, answer:'answer', steps:['step'], checks:['check'], boundary:'verify', sources:[source(s, papers.find(p=>p.id===s).doi)], documentation:[{label:'docs',url:'https://docs.lammps.org/Manual.html',locator:'manual'}], tags:['topic']});
const data = {schema_version:1, as_of:'2026-10-20', cards:[mk('faq','faq','diffusion workflow',['diffusion','MSD'],[['diffusion']], 'p2')]};
let out = lookup('diffusion', papers, data); assert.equal(out.cards[0].id, 'faq'); assert.equal(out.cards[0].sources[0].title, 'Workflow paper');
assert.equal(lookup('unknown nonsense', papers, data).cards.length, 0);
assert.equal(lookup('MD inside MDP', papers, {...data, cards:[mk('md','foundation','md',['md'],[['MD']], 'p1')]}).cards.length, 0);
assert.equal(lookup('diffusion', papers, data, {limit:1}).cards.length, 1);
assert.equal(lookup('MSD', papers, {...data, cards:[mk('neb','faq','NEB',['NEB'],[['NEB'],['端点']], 'p1')]}).cards.length, 0);
assert.equal(lookup('diffusion', [{id:'p1',doi:'10.1000/ABC',title:'T'}, null], data).cards.length, 0);
assert.deepEqual(lookup('diffusion', papers, data).coverage, {cards:1});
assert.equal(lookup('计算', papers, {...data, cards:[{...data.cards[0], private_key:1}]}).cards.length, 0);
assert.equal(lookup('计算', papers, {...data, cards:[{...data.cards[0], sources:[source('p1','10.1000/wrong')]}]}).cards.length, 0);
const catalog = JSON.parse(fs.readFileSync(new URL('../data/papers.json', import.meta.url), 'utf8'));
const knowledge = JSON.parse(fs.readFileSync(new URL('../data/research_knowledge.json', import.meta.url), 'utf8'));
for (const card of knowledge.cards) {
  for (const question of [card.question, ...card.aliases]) {
    assert.equal(lookup(question, catalog, knowledge).cards[0]?.id, card.id, `top-hit mismatch for ${card.id}: ${question}`);
  }
}
assert.equal(lookup('完全无关的未知提问 xyzzy', catalog, knowledge).cards.length, 0);
console.log('research knowledge lookup tests passed');
