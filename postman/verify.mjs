import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const collection = JSON.parse(fs.readFileSync(new URL('./Inventario-U-Canary.postman_collection.json', import.meta.url)));
const environment = JSON.parse(fs.readFileSync(new URL('./OCI-plantilla.postman_environment.json', import.meta.url)));
const requests = collection.item.flatMap(folder => folder.item);
assert.equal(requests.length, 12);
for (const request of requests) {
  for (const event of request.event) new vm.Script(event.script.exec.join('\n'));
}
for (const key of ['team_api_key', 'grafana_password']) {
  assert.equal(environment.values.find(value => value.key === key).value, '');
}

const variables = new Map();
const store = { get: key => variables.get(key), set: (key, value) => variables.set(key, value) };
let skipped = false;
const pm = {
  collectionVariables: store,
  environment: { get: () => 'false' },
  execution: { skipRequest: () => { skipped = true; } },
  test: (_name, callback) => callback(),
};
const injection = requests.find(item => item.name.startsWith('Activar'));
const guard = injection.event.find(event => event.listen === 'prerequest').script.exec.join('\n');
vm.runInNewContext(guard, { pm, console: { log() {} } });
assert.equal(skipped, true, 'Fault injection must be disabled by default');
skipped = false;
pm.environment.get = () => 'true';
vm.runInNewContext(guard, { pm, console: { log() {} } });
assert.equal(skipped, false);

const counter = requests.find(item => item.name.startsWith('Enviar lectura'));
const countScript = counter.event.find(event => event.listen === 'test').script.exec.join('\n');
function response(track, code) {
  pm.response = { code, headers: { get: name => ({
    'X-App-Track': track,
    'X-App-Version': track === 'stable' ? '2.0.0' : '3.0.0',
    'X-App-Revision': 'a'.repeat(40),
  })[name] } };
  vm.runInNewContext(countScript, { pm, console: { log() {} } });
}
response('stable', 200);
response('canary', 500);
assert.equal(variables.get('public_total'), 2);
assert.equal(variables.get('public_stable'), 1);
assert.equal(variables.get('public_canary'), 1);
assert.equal(variables.get('canary_5xx'), 1);
assert.throws(() => response('stable', 500), /Fallo inesperado en stable/);
assert.throws(() => response('unmatched', 200), /Track ausente/);
console.log('Postman: 12 requests, valid scripts, private placeholders, guarded faults and correct counters');
