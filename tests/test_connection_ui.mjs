import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1].replace(/\n\s*loadData\(\);\s*$/, '\n');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {value:'', innerHTML:'', textContent:'', disabled:false, checked:false,
    classList:{add(){},remove(){},toggle(){}},addEventListener(){}});
  return nodes.get(id);
}
const stored = new Map([['battery-agent-api-token', 'legacy-fixture']]);
const reads = [], writes = [], removed = [];
const store = {
  getItem(key) { reads.push(key); return stored.get(key) || ''; },
  setItem(key, value) { writes.push(key); stored.set(key, value); },
  removeItem(key) { removed.push(key); stored.delete(key); },
};
const requests = [];
let release, releaseBody;
let delayedBody = false;
const context = vm.createContext({URL, URLSearchParams, console, FormData, location:{protocol:'https:',hostname:'example.github.io',search:''},
  document:{querySelector(s){return node(s.slice(1));},querySelectorAll(){return [];}}, window:{},
  localStorage:store, sessionStorage:store, navigator:{}, alert(){},
  fetch(url, options) { requests.push({url, options}); return new Promise(resolve => {release = () => resolve({ok:true,json(){return delayedBody ? new Promise(done => {releaseBody = done;}) : Promise.resolve({});}});}); },
});
vm.runInContext(source, context);
assert.equal(context.window.state.apiToken, '');
assert.equal(reads.includes('battery-agent-api-token'), false, 'legacy token is never loaded');
assert.ok(removed.includes('battery-agent-api-token'));
node('apiBase').value = 'https://service.example'; node('apiToken').value = 'memory-only-fixture';
vm.runInContext('saveConnection()', context);
assert.equal(context.window.state.apiToken, 'memory-only-fixture');
assert.equal(writes.includes('battery-agent-api-token'), false, 'token is never written to storage');
vm.runInContext('closeUploadModal()', context);
assert.equal(node('apiToken').value, '');
assert.equal(context.window.state.apiToken, 'memory-only-fixture', 'closing settings does not unexpectedly disconnect active use');
const pending = vm.runInContext('apiFetch("/api/papers")', context);
assert.equal(requests[0].options.headers.Authorization, 'Bearer memory-only-fixture');
vm.runInContext('disconnectApi()', context);
release();
await assert.rejects(pending, /连接已变更/);
assert.equal(context.window.state.apiToken, '');
assert.equal(context.window.state.apiBase, '');
assert.equal(vm.runInContext('hasBackend()', context), false);
assert.equal(node('apiToken').value, '');
assert.match(node('serviceMessage').textContent, /已断开/);
node('apiBase').value = 'https://service.example'; node('apiToken').value = 'late-body-fixture';
vm.runInContext('saveConnection()', context);
delayedBody = true;
const headersPending = vm.runInContext('apiFetch("/api/papers")', context);
release();
const response = await headersPending;
const bodyPending = response.json();
vm.runInContext('disconnectApi()', context);
releaseBody({privateFixture: true});
await assert.rejects(bodyPending, /连接已变更/, 'disconnect rejects data whose headers arrived before disconnect');
assert.equal(context.window.state.backendConnected, false);
assert.equal(Object.keys(context.window.state.methods).length, 0);
for (const bad of ['http://remote.example', 'https://user:password@example.test', 'https://example.test/?key=fixture', 'javascript:alert(1)']) {
  node('apiBase').value = bad;
  assert.throws(() => vm.runInContext('saveConnection()', context));
}
console.log('connection memory-only token, explicit disconnect, stale response and URL safety tests passed');
