import fs from 'node:fs';
import assert from 'node:assert/strict';

const html = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
const staticMap = JSON.parse(fs.readFileSync(new URL('../static/data/battery_components.json', import.meta.url), 'utf8'));
const sourceMap = JSON.parse(fs.readFileSync(new URL('../data/battery_components.json', import.meta.url), 'utf8'));
const catalog = JSON.parse(fs.readFileSync(new URL('../data/papers.json', import.meta.url), 'utf8'));

assert.match(html, /<link[^>]+href="\.\/battery_explorer\.css"/);
assert.match(html, /<script[^>]+src="\.\/battery_explorer\.js"/);
assert.match(html, /id="batteryExplorer"/);
assert.match(html, /typeof window\.BatteryExplorer\?\.mount !== 'function'/);
assert.match(html, /fetch\('\.\/data\/battery_components\.json'/);
assert.match(html, /BatteryExplorer\.mount\(root/);
assert.match(html, /if \(typeof batteryMapCleanup === 'function'\) batteryMapCleanup\(\)/);
assert.deepEqual(staticMap, sourceMap, 'static deployment asset must match curated source map');
assert.equal(staticMap.components.length, 6);
const refs = staticMap.components.flatMap((component) => component.papers);
assert.equal(refs.length, 76);
assert.equal(new Set(refs.map((ref) => ref.paper_id)).size, 74);
for (const ref of refs) {
  const canonical = catalog.find((paper) => paper.id === ref.paper_id);
  assert.ok(canonical, `missing canonical paper ${ref.paper_id}`);
  assert.equal(ref.doi, canonical.doi, `stale DOI for ${ref.paper_id}`);
}
console.log('Battery explorer integration: guarded optional mount, asset paths, copied map, 76 refs/74 papers PASS');
