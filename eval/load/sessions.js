import http from 'k6/http';
import { sleep } from 'k6';
import exec from 'k6/execution';
import encoding from 'k6/encoding';
import { SharedArray } from 'k6/data';
import { Counter, Rate, Trend } from 'k6/metrics';

// Run locally with k6. No remote JS imports and no credentials in result files.
function number(name, fallback, min, max, integer = true) {
  const value = Number(__ENV[name] === undefined ? fallback : __ENV[name]);
  if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
    throw new Error(`${name} must be ${integer ? 'an integer' : 'a number'} from ${min} to ${max}`);
  }
  return value;
}

const PROFILE = __ENV.PROFILE || 'smoke';
if (!['smoke', 'elasticity', 'contention', 'read_only_smoke', 'read_only_elasticity'].includes(PROFILE)) {
  throw new Error('Unknown PROFILE');
}
const READ_ONLY = PROFILE.startsWith('read_only_');
const SMOKE = PROFILE === 'smoke' || PROFILE === 'read_only_smoke';
const SHARED_ACCOUNT = READ_ONLY || PROFILE === 'contention';
const BASE_URL = (__ENV.BASE_URL || '').replace(/\/$/, '');
if (!/^https:\/\/[^/?#]+$/.test(BASE_URL)) throw new Error('BASE_URL must be an HTTPS origin, without /api');
const PEAK = SMOKE ? 1 : number('PEAK_VUS', 50, 21, 100);
const BASELINE = SMOKE ? 1 : number('BASELINE_VUS', 5, 1, Math.min(20, PEAK - 1));
// Fixed, seeded catalogue ID: Tomato and egg rice bowls. No session creation is needed to discover it.
const READ_RECIPE_ID = (__ENV.READ_RECIPE_ID || '645a8d38-bfae-47f2-b00e-3ca6828a964e').toLowerCase();
if (READ_ONLY && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(READ_RECIPE_ID)) {
  throw new Error('READ_RECIPE_ID must be a canonical recipe UUID');
}
const MID = Math.max(21, Math.ceil(PEAK / 2));
const THINK = number('THINK_SECONDS', 2, 0.25, 10, false);
const MAX_ITERATIONS = number('MAX_ITERATIONS', READ_ONLY ? 6000 : 5000, 1, 10000);
const TIMEOUT = number('REQUEST_TIMEOUT_SECONDS', 10, 1, 30);
const P95_MS = number('P95_MS', 2000, 100, 30000);
const HOLD = number('HOLD_SECONDS', 120, 30, 600);
const RESULT_PREFIX = __ENV.RESULT_PREFIX;
if (!RESULT_PREFIX) throw new Error('Set RESULT_PREFIX to a new path in the ignored private/ directory');
const PHASES = SMOKE
  ? [{ name: 'smoke', seconds: 20, target: 1 }]
  : [
    { name: 'baseline', seconds: 60, target: BASELINE },
    { name: 'ramp_mid', seconds: 30, target: MID },
    { name: 'mid', seconds: 60, target: MID },
    { name: 'ramp_peak', seconds: 30, target: PEAK },
    { name: 'peak', seconds: HOLD, target: PEAK },
    { name: 'ramp_down', seconds: 30, target: BASELINE },
    { name: 'recovery', seconds: 60, target: BASELINE },
    { name: 'stop', seconds: 10, target: 0 },
  ];
const DURATION = PHASES.reduce((total, phase) => total + phase.seconds, 0);
const accounts = new SharedArray('test accounts', () => {
  let rows;
  if (__ENV.COOKISH_ID_TOKEN) {
    if (!SHARED_ACCOUNT && PEAK > 1) throw new Error('Independent-household elasticity requires TOKENS_FILE, not one token');
    rows = [{ id_token: __ENV.COOKISH_ID_TOKEN }];
  } else {
    if (!__ENV.TOKENS_FILE) throw new Error('Set COOKISH_ID_TOKEN for one-account profiles, or TOKENS_FILE for multiple accounts');
    try { rows = JSON.parse(open(__ENV.TOKENS_FILE)); }
    catch (_) { throw new Error('Could not read a JSON array from TOKENS_FILE'); }
  }
  if (!Array.isArray(rows) || rows.length < (SHARED_ACCOUNT ? 1 : PEAK)) {
    throw new Error('Need one account per peak VU, or one account for read-only/contention profiles');
  }
  return rows.slice(0, SHARED_ACCOUNT ? 1 : PEAK).map((row) => {
    if (typeof row.id_token !== 'string' || row.id_token.split('.').length !== 3) {
      throw new Error('Each account must contain a Cognito id_token');
    }
    return { id_token: row.id_token };
  });
});

const errors = new Rate('api_error_rate');
const latency = new Trend('api_latency_ms', true);
const tagLatency = new Trend('tag_adjustment_ms', true);
const cookCreated = new Counter('cook_sessions_created');
const shopCreated = new Counter('shop_sessions_created');
const completed = new Counter('workflows_completed');
const ROUTES = READ_ONLY ? ['inventory', 'recipe']
  : ['inventory', 'cook_create', 'tag_adjust', 'people_adjust', 'recipe', 'shop_create', 'shop_adjust'];
const thresholds = {
  api_error_rate: ['rate<0.01'],
  workflows_completed: ['count>0'],
};
if (!READ_ONLY) {
  thresholds.tag_adjustment_ms = [{ threshold: `p(95)<${P95_MS}`, abortOnFail: true, delayAbortEval: '30s' }];
}
// Explicit submetrics retain per-route and per-phase percentiles in the JSON summary.
for (const route of ROUTES) {
  thresholds[`api_latency_ms{route:${route}}`] = READ_ONLY
    ? [{ threshold: `p(95)<${P95_MS}`, abortOnFail: true, delayAbortEval: '30s' }]
    : ['p(95)>=0'];
}
for (const phase of PHASES.filter((p) => !p.name.startsWith('ramp') && p.name !== 'stop')) {
  thresholds[`api_latency_ms{phase:${phase.name}}`] = ['p(95)>=0'];
}
if (!SMOKE) {
  if (!READ_ONLY) {
    thresholds.cook_sessions_created = [`count>=${PEAK}`];
    thresholds.shop_sessions_created = [`count>=${PEAK}`];
  }
  thresholds['workflows_completed{phase:peak}'] = ['count>0'];
  thresholds['workflows_completed{phase:recovery}'] = ['count>0'];
}

export const options = {
  scenarios: {
    sessions: {
      executor: 'ramping-vus',
      startVUs: BASELINE,
      stages: PHASES.map((p) => ({ duration: `${p.seconds}s`, target: p.target })),
      gracefulRampDown: '15s',
      gracefulStop: '15s',
    },
  },
  setupTimeout: '180s',
  maxRedirects: 0,
  summaryTrendStats: ['min', 'med', 'p(95)', 'p(99)', 'max', 'count'],
  systemTags: ['status', 'method', 'name', 'scenario', 'expected_response', 'error_code'],
  thresholds,
};

function phaseName() {
  let elapsed = (Date.now() - exec.scenario.startTime) / 1000;
  for (const phase of PHASES) {
    if (elapsed < phase.seconds) return phase.name;
    elapsed -= phase.seconds;
  }
  return 'stop';
}

function request(token, method, path, body, route, expected, phase = phaseName()) {
  if (READ_ONLY && method !== 'GET') throw new Error('Read-only profiles must not submit writes');
  const response = http.request(method, `${BASE_URL}${path}`, body === null ? null : JSON.stringify(body), {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    timeout: `${TIMEOUT}s`,
    tags: { name: route, route, phase },
    responseType: 'text',
  });
  if (phase !== 'preflight') {
    latency.add(response.timings.duration, { route, phase });
    if (route === 'tag_adjust') tagLatency.add(response.timings.duration, { phase });
  }
  let data;
  try { data = response.json(); } catch (_) { data = null; }
  const bad = response.status !== expected || !data || typeof data !== 'object';
  errors.add(bad, { route, phase });
  if (bad) {
    // Abort globally on the first failed request: no retry storm or hidden NO_RESULT.
    // Do not print the response body, URL containing a record ID, or token.
    exec.test.abort(`Stopped at ${route}: HTTP ${response.status}; inspect server logs for the UTC test window`);
  }
  return data;
}

export function setup() {
  const households = new Set();
  const users = new Set();
  // JWT decoding here checks lifetime only. API Gateway still verifies every token.
  for (const account of accounts) {
    let claims;
    try { claims = JSON.parse(encoding.b64decode(account.id_token.split('.')[1], 'rawurl', 's')); }
    catch (_) { throw new Error('Invalid token payload'); }
    if (claims.token_use !== 'id' || typeof claims.sub !== 'string' || !Number.isFinite(claims.exp)
      || claims.exp * 1000 < Date.now() + (DURATION + 180 + 60) * 1000) {
      throw new Error('Use a fresh Cognito ID token valid through setup, load and recovery');
    }
    if (READ_ONLY) {
      const inventory = request(account.id_token, 'GET', '/api/inventory', null, 'inventory', 200, 'preflight');
      if (!Array.isArray(inventory.groups)) exec.test.abort('Read fixture returned invalid inventory');
      const recipe = request(account.id_token, 'GET', `/api/recipes/${READ_RECIPE_ID}`, null, 'recipe', 200, 'preflight');
      if (recipe.id !== READ_RECIPE_ID || !Array.isArray(recipe.steps)) exec.test.abort('Read fixture is not a seeded recipe');
      users.add(claims.sub);
      continue;
    }
    const me = request(account.id_token, 'GET', '/api/me', null, 'me', 200, 'preflight');
    if (!me.user || !me.household || !me.preferences) {
      exec.test.abort('Complete test-account onboarding before the run');
    }
    users.add(me.user.id);
    households.add(me.household.id);
  }
  if (PROFILE === 'elasticity' && (users.size !== PEAK || households.size !== PEAK)) {
    exec.test.abort('Elasticity requires distinct accounts AND distinct households, one per peak VU');
  }
  console.log(JSON.stringify({ event: 'load_preflight', utc: new Date().toISOString(), profile: PROFILE,
    accounts: users.size, households: READ_ONLY ? 'one pre-existing test household (operator supplied)' : households.size,
    peak_vus: PEAK, scheduled_seconds: DURATION }));
}

// These bindings belong to one VU. Sessions are reused to bound database growth.
let cookSession;
let shopSession;
let people;
let alternatePeople;

export default function () {
  if (exec.scenario.iterationInTest >= MAX_ITERATIONS) {
    exec.test.abort('Iteration cap reached; this is an incomplete run, not a passing elasticity result');
  }
  const token = accounts[SHARED_ACCOUNT ? 0 : exec.vu.idInTest - 1].id_token;
  request(token, 'GET', '/api/inventory', null, 'inventory', 200);
  if (READ_ONLY) {
    request(token, 'GET', `/api/recipes/${READ_RECIPE_ID}`, null, 'recipe', 200);
    completed.add(1, { phase: phaseName() });
    sleep(THINK);
    return;
  }
  if (!cookSession) {
    const suggestion = request(token, 'POST', '/api/cook/sessions', {}, 'cook_create', 201);
    if (!suggestion.session_id || !Number.isInteger(suggestion.people)) exec.test.abort('Invalid Cook response');
    cookSession = suggestion.session_id;
    people = suggestion.people;
    alternatePeople = people === 12 ? 11 : people + 1;
    cookCreated.add(1);
  }
  // One tag request plus two portion refinements. Repeating the tag does not accumulate new constraints.
  request(token, 'POST', `/api/cook/sessions/${cookSession}/adjust`, { tags: ['less_oil'] }, 'tag_adjust', 200);
  request(token, 'POST', `/api/cook/sessions/${cookSession}/adjust`, { people: alternatePeople }, 'people_adjust', 200);
  const suggestion = request(token, 'POST', `/api/cook/sessions/${cookSession}/adjust`, { people }, 'people_adjust', 200);
  if (!suggestion.recipe || !suggestion.recipe.id) exec.test.abort('Invalid suggestion response');
  request(token, 'GET', `/api/recipes/${suggestion.recipe.id}`, null, 'recipe', 200);
  if (!shopSession) {
    const basket = request(token, 'POST', '/api/shop/sessions', {}, 'shop_create', 201);
    if (!basket.session_id) exec.test.abort('Invalid Shop response');
    shopSession = basket.session_id;
    shopCreated.add(1);
  }
  request(token, 'POST', `/api/shop/sessions/${shopSession}/adjust`, { people }, 'shop_adjust', 200);
  completed.add(1, { phase: phaseName() });
  sleep(THINK);
}

export function handleSummary(data) {
  // Whitelist fields: never serialize accounts, setup data, headers or environment variables.
  const report = {
    finished_utc: new Date().toISOString(),
    profile: PROFILE, peak_vus: PEAK, phases: PHASES,
    workload: READ_ONLY ? 'Authenticated inventory and recipe GETs; one pre-existing household'
      : 'Cook/Shop sessions and refinements',
    read_recipe_id: READ_ONLY ? READ_RECIPE_ID : null,
    think_seconds: THINK, request_timeout_seconds: TIMEOUT, max_iterations: MAX_ITERATIONS,
    latency_target_ms: P95_MS,
    notes: 'Client metrics only. Correlate with CloudWatch; VUs and saved sessions are not Lambda concurrency.',
    metrics: data.metrics, state: data.state,
  };
  const failures = Object.entries(data.metrics).flatMap(([metric, result]) =>
    Object.entries(result.thresholds || {}).filter(([, value]) => !value.ok).map(([rule]) => `${metric}: ${rule}`));
  return {
    [`${RESULT_PREFIX}-summary.json`]: JSON.stringify(report, null, 2),
    stdout: `\n${PROFILE}: completed ${data.metrics.workflows_completed?.values.count || 0} workflows.\n`
      + `Failed thresholds: ${failures.length ? failures.join('; ') : 'none'}\n`
      + `Summary: ${RESULT_PREFIX}-summary.json. Check k6 exit status and CloudWatch before interpreting results.\n`,
  };
}
