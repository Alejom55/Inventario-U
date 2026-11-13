import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

export const options = JSON.parse(open('./profile.json'));
const complete = new Rate('flow_complete');
const duration = new Trend('flow_duration', true);
const base = (__ENV.CHAOS_TARGET_URL || '').replace(/\/$/, '');
const round = __ENV.CHAOS_ROUND;
const runId = __ENV.CHAOS_RUN_ID || '';
if (!['R0', 'R1'].includes(round) || !base || !__ENV.TEAM_API_KEY) {
  throw new Error('Declare CHAOS_TARGET_URL, CHAOS_ROUND=R0|R1 y TEAM_API_KEY');
}
if (!/^[a-f0-9]{40}$/.test(__ENV.EXPECTED_APP_REVISION || '')) {
  throw new Error('Declare EXPECTED_APP_REVISION con el SHA instalado');
}
for (const key of ['SKU_ID', 'ALMACEN_ID', 'DEPORTISTA_ID', 'ARTICULO_ID']) {
  if (!__ENV[key]) throw new Error(`Falta identificador sintetico: ${key}`);
}
if (__ENV.CHAOS_WINDOW_ACK !== 'GROUP_SYNTHETIC_ONLY') {
  throw new Error('Falta acuerdo de ventana y datos sinteticos');
}
const windowStart = Date.parse(__ENV.CHAOS_WINDOW_START_UTC || '');
const windowEnd = Date.parse(__ENV.CHAOS_WINDOW_END_UTC || '');
if (!/^[a-f0-9]{32}$/.test(runId) || !Number.isFinite(windowStart) || !Number.isFinite(windowEnd) || windowStart >= windowEnd) {
  throw new Error('Declare run ID unico y ventana UTC valida');
}
const parameters = {
  sku_id: __ENV.SKU_ID, almacen_id: __ENV.ALMACEN_ID,
  deportista_id: __ENV.DEPORTISTA_ID, articulo_id: __ENV.ARTICULO_ID,
};
const query = Object.entries(parameters).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
function identityAt(entity, selector) {
  for (const field of (selector || 'id').split('.')) {
    if (!entity || typeof entity !== 'object') return undefined;
    entity = entity[field];
  }
  return typeof entity === 'string' || typeof entity === 'number' ? String(entity) : undefined;
}

export default function () {
  if (Date.now() < windowStart || Date.now() >= windowEnd) {
    exec.test.abort('Fuera de la ventana acordada; no se enviaran mas peticiones');
  }
  const trace = `chaos-${runId}-${round}-${exec.vu.idInTest}-${exec.scenario.iterationInTest}`;
  const response = http.get(`${base}/api/v2/integracion?${query}`, {
    headers: { 'X-Api-Key': __ENV.TEAM_API_KEY, 'X-Trace-Id': trace },
    timeout: '12s',
    tags: { name: 'flow-three-apis', round, phase: exec.scenario.name },
  });
  let body = {};
  try { body = response.json(); } catch (_) { /* A non-JSON error is an incomplete flow. */ }
  const ok = check(response, {
    'flujo completo y correlacionado': r => r.status === 200 && body.trace_id === trace &&
      body.inventario !== undefined && body.deportista !== undefined && body.articulo !== undefined &&
      String(body.inventario?.sku_id) === __ENV.SKU_ID && String(body.inventario?.almacen_id) === __ENV.ALMACEN_ID &&
      identityAt(body.deportista, __ENV.DEPORTBACK_ID_FIELD) === __ENV.DEPORTISTA_ID &&
      identityAt(body.articulo, __ENV.FASTIFY_ID_FIELD) === __ENV.ARTICULO_ID &&
      r.headers['X-Chaos-Round'] === round && r.headers['X-App-Revision'] === __ENV.EXPECTED_APP_REVISION &&
      r.headers['X-Resilience-Mode'] === (round === 'R0' ? 'baseline' : 'protected'),
  });
  complete.add(ok, { round, phase: exec.scenario.name });
  duration.add(response.timings.duration, { round, phase: exec.scenario.name });
}

export function handleSummary(data) {
  return { [`chaos/results/k6-${round}.json`]: JSON.stringify({
    round, run_id: runId, expected_revision: __ENV.EXPECTED_APP_REVISION,
    instrument: 'k6', profile: options, captured_at_utc: new Date().toISOString(),
    metrics: data.metrics,
  }, null, 2) };
}
