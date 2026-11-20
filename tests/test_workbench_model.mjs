import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import workbench from '../static/workbench-model.js';
const { create } = workbench;
const testSignedUrl = new URL('https://example.org/');
testSignedUrl.searchParams.set('token', 'synthetic-fixture-value');

const model = create({
  papers: [
    { id: 'dom', title: 'DFT and NEB study', authors: [{ name: 'A', institution: '北京大学材料学院' }], year: 2024, methods: ['DFT', 'NEB', 'VASP'], summary: 'solid electrolyte', document_type: 'Paper', doi: '10.1/dom', evidence_card: { metrics: [{ label: 'barrier', value: 0.22, unit: 'eV', source: 'article', locator: 'Fig. 2' }, { label: 'unanchored', value: 3 }] }, resources: [{ url: 'https://example.org/read' }, { url: 'http://unsafe.example/x' }, { url: testSignedUrl.href }] },
    { id: 'intl', title: 'AIMD electrolyte', authors: [{ name: 'B', institution: 'University of Example, USA' }], year: 2022, methods: ['AIMD', 'LAMMPS'], summary: 'liquid electrolyte' },
    { id: 'unknown', title: 'Materials Studio mention in title', year: 2020, methods: ['DFT'], protocol_steps: ['Try LAMMPS for comparison'] }
  ],
  tags: { papers: { dom: { display_tags: ['DFT', 'NEB'], method_tags: ['DFT', 'NEB'] }, unknown: { display_tags: ['MS'] } } },
  titles: { papers: { dom: { title_zh: '正极迁移' } } },
  domestic: { entries: [{ paper_id: 'dom', authors_basis: [{ institution: '北京大学', region: '中国内地' }] }] },
  components: { components: [{ id: 'cathode', papers: [{ paper_id: 'dom' }] }, { id: 'electrolyte', papers: [{ paper_id: 'intl' }] }] },
  insights: { papers: {
    dom: {
      sources: [{ id: 'article', scope: 'article', locator: 'PDF p. 4, Fig. 2', url: 'https://example.org/article' }],
      sections: { methods: [{ text: 'NEB protocol', kind: 'reported', source_refs: ['article'] }] },
    },
  } }
});

assert.ok(model.byId instanceof Map);
assert.equal(model.byId.get('dom').region, 'domestic');
assert.equal(model.byId.get('intl').region, 'unknown');
assert.equal(model.byId.get('unknown').region, 'unknown');
assert.deepEqual(model.byId.get('dom').methods_normalized, ['DFT', 'NEB']);
assert.ok(!model.byId.get('unknown').software_normalized.includes('MS'), 'title/curated display tag alone cannot establish software');
assert.ok(!model.byId.get('unknown').software_normalized.includes('LAMMPS'), 'replication suggestions do not establish software use');
assert.equal(model.byId.get('dom').title_zh, '正极迁移');
assert.equal(model.byId.get('dom').links.length, 2, 'doi and safe resource only');
assert.equal(model.card('dom').sections.observables.metrics.length, 1);
assert.equal(model.byId.get('dom').evidence_coverage.article, true);
assert.equal(model.byId.get('dom').evidence_coverage.quantitative, true);
assert.equal(model.query({ evidence: 'article' }).rows.length, 1);
assert.equal(model.query({ evidence: 'quantitative' }).rows.length, 1);
assert.equal(model.query({ evidence: 'article', regions: ['unknown'] }).rows.length, 0);
assert.equal(model.query({ evidence: 'constructor' }).rows.length, 0);
assert.equal(model.card('dom').sections.protocol.software.includes('VASP'), true);
assert.equal(model.query({ methods: ['NEB'] }).rows[0].id, 'dom');
assert.equal(model.query({ regions: ['international'] }).rows.length, 0);
assert.equal(model.query({ components: ['cathode'] }).rows[0].id, 'dom');
assert.equal(model.card('missing'), null);
assert.equal(model.safeLink('javascript:alert(1)'), null);
assert.equal(model.safeLink('/paper.html\n#dom'), null);
assert.equal(model.safeLink('https://example.org/?api_key=x'), null);
assert.equal(model.safeLink('/paper.html#dom'), '/paper.html#dom');
assert.equal(model.safeLink('//evil.example/x'), null);
assert.equal(model.safeLink('\\\\evil.example\\x'), null);
assert.equal(model.query({ sort: 'year-asc' }).rows[0].id, 'unknown');
assert.equal(model.query({ sort: 'title' }).rows[0].id, 'intl');

const articleSource = {id:'body', scope:'article', locator:'Fig. 2', url:'https://example.org/article'};
const reported = {text:'A reported result', kind:'reported', source_refs:['body']};
const unsupported = create({
  papers: [
    {id:'source_only'},
    {id:'advice'},
    {id:'abstract_only'},
    {id:'unlocated'},
    {id:'blank'},
    {id:'missing_metric', evidence_card:{metrics:[{label:'Barrier', value:1, source:'Body'}]}},
    {id:'zero_metric', evidence_card:{metrics:[{label:'Barrier', value:0, source:'Body', locator:'Fig. 2'}]}},
  ],
  insights:{papers:{
    source_only:{sources:[articleSource]},
    advice:{sources:[articleSource], sections:{methods:[{...reported, kind:'reading_guide'}]}},
    abstract_only:{sources:[{...articleSource, scope:'abstract'}], sections:{findings:[reported]}},
    unlocated:{sources:[{...articleSource, locator:' '}], sections:{findings:[reported]}},
    blank:{sources:[articleSource], sections:{findings:[{...reported, text:' '}]}}
  }}
});
assert.deepEqual(unsupported.query({evidence:'article'}).rows, []);
assert.deepEqual(unsupported.query({evidence:'quantitative'}).rows.map(p => p.id), ['zero_metric']);

const canonical = name => JSON.parse(fs.readFileSync(new URL(`../data/${name}`, import.meta.url), 'utf8'));
const canonicalComponents = canonical('battery_components.json');
const canonicalTags = canonical('paper_tags.json');
const canonicalPapers = canonical('papers.json');
const canonicalDomestic = canonical('domestic_papers.json');
const canonicalModel = create({ papers: canonicalPapers, tags: canonicalTags, titles: canonical('paper_titles_zh.json'), components: canonicalComponents, domestic: canonicalDomestic, insights: canonical('paper_insights.json') });
assert.ok(canonicalModel.papers.length >= 273);
assert.equal(canonicalModel.papers.reduce((n, p) => n + p.component_ids.length, 0), canonicalComponents.components.reduce((n, c) => n + c.papers.length, 0), 'all component registry relations retained, including overlaps');
assert.ok(canonicalModel.facets.components.some(x => x.value === 'separator'));
assert.equal(canonicalModel.query({type:'方法论文'}).rows.length, canonicalTags.counts['方法论文']);
assert.equal(canonicalModel.query({type:'综述'}).rows.length, canonicalTags.counts['综述']);
const domesticIds = new Set([
  ...canonicalDomestic.entries.map(p => p.paper_id),
  ...canonicalPapers.filter(p => p.region === 'domestic').map(p => p.id),
]);
assert.deepEqual(new Set(canonicalModel.query({region:'domestic'}).rows.map(p => p.id)), domesticIds);
const browserCode = fs.readFileSync(new URL('../static/browser_agent.js', import.meta.url), 'utf8');
const browserContext = vm.createContext({ window: {} }); vm.runInContext(browserCode, browserContext);
const modelWithSearch = create({ papers: canonical('papers.json'), tags: canonical('paper_tags.json'), titles: canonical('paper_titles_zh.json'), components: canonicalComponents, searchAgent: browserContext.window.BatteryBrowserAgent, searchConfig: canonical('search_config.json') });
const expanded = modelWithSearch.query({ q: 'AI for Science' });
assert.ok(expanded.expandedTerms.includes('ai4science'));
assert.ok(expanded.rows[0].retrieval?.reason, 'searchDetailed retrieval reason retained');
assert.equal(modelWithSearch.query({ q: 'AI for Science', sort: 'year-asc' }).rows.at(-1).year >= modelWithSearch.query({ q: 'AI for Science', sort: 'year-asc' }).rows[0].year, true);
console.log('Workbench model: normalization, strict facets, evidence metrics and link safety PASS');
