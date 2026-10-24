import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('../static/paper_insights.js', import.meta.url), 'utf8');
const context = { window: {}, URL, location: { href: 'https://example.test/' } };
vm.createContext(context); vm.runInContext(source, context);
const api = context.window.PaperInsights;
const data = {schema_version:1,as_of:'2026-10-25',methodology:{reference_title:'Cai et al.',reference_url:'https://doi.org/10.1234/ref',implemented_layers:'L1-L4',note:'Public reading aid.'},papers:{'cai-2024':{paper_id:'cai-2024',doi:'10.1234/example',sources:[{id:'s',url:'https://doi.org/10.1234/example',scope:'article',locator:'p. 2'}],sections:{findings:[{text:'<safe>',source_refs:['s'],kind:'reported'}]},relations:[]}}};
assert.ok(api.setData(data));
const html = api.renderHtml('cai-2024');
assert.match(html, /&lt;safe&gt;/); assert.match(html, /p\. 2/); assert.equal(api.renderHtml('missing'), '');
const malformed = structuredClone(data);
malformed.papers['cai-2024'].sources[0].locator = '';
assert.equal(api.normalize(malformed), null);
const badKind = structuredClone(data);
badKind.papers['cai-2024'].sections.findings[0].kind = 'invented';
assert.equal(api.normalize(badKind), null);

// The browser-side normalizer must enforce the same public-data invariants as
// validate_paper_insights.py, rather than merely checking string shape.
const impossibleDate = structuredClone(data);
impossibleDate.as_of = '2026-99-99';
assert.equal(api.normalize(impossibleDate), null, 'impossible calendar dates are rejected');
const privateReference = structuredClone(data);
privateReference.methodology.reference_url = 'http://example.test/method';
assert.equal(api.normalize(privateReference), null, 'methodology reference must be HTTPS');
const malformedPaper = structuredClone(data);
malformedPaper.papers['cai-2024'] = null;
assert.equal(api.normalize(malformedPaper), null, 'dataset with only malformed papers is rejected');

// Keep the async insight load from leaving an already-open paper modal stale.
const indexHtml = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
assert.match(indexHtml, /PaperInsights\?\.load\('\.\/data\/paper_insights\.json', state\.papers\)[\s\S]*?state\.openPaperId[\s\S]*?showPaper\(state\.openPaperId\)/, 'canonical-checked async insight load repaints open modal');
assert.equal((indexHtml.match(/PaperInsights\?\.load\(/g) || []).length, 1, 'only one insight load can update the modal');

// The published docs copy is a deployment artifact and must stay byte-identical
// to static for both code and the curated insight payload.
for (const asset of ['paper_insights.js', 'paper_insights.css']) {
  assert.equal(fs.readFileSync(new URL(`../static/${asset}`, import.meta.url), 'utf8'),
    fs.readFileSync(new URL(`../docs/${asset}`, import.meta.url), 'utf8'), `${asset} static/docs parity`);
}
assert.deepEqual(JSON.parse(fs.readFileSync(new URL('../static/data/paper_insights.json', import.meta.url), 'utf8')),
  JSON.parse(fs.readFileSync(new URL('../docs/data/paper_insights.json', import.meta.url), 'utf8')), 'paper insights JSON static/docs parity');
console.log('paper insights UI checks passed');
