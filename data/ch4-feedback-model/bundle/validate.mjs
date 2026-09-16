/**
 * validate.mjs - check ch4feedback.js against the Python reference.
 *
 *   node validate.mjs
 *
 * Two implementations of the same model is a liability unless something keeps
 * them honest. build_bundle.py emits validation_fixtures.json from the Python;
 * this replays every case in JavaScript and fails loudly on any drift. Both
 * use fixed-step RK4 with the same substep count, so agreement should be at
 * round-off, not "close enough".
 */
import { readFileSync } from 'node:fs';
// Resolve data next to THIS file, not the current working directory, so the
// harness runs from anywhere (npm scripts at the repo root, CI, a subdir).
const here = (rel) => new URL(rel, import.meta.url);
import {
  run, runDecomposed, DEFAULTS, paramsFromBundle, climateParams,
  feedbackWm2PerK, rebaseTemperature, listScenarios, CONST,
} from './ch4feedback.js';

const bundle = JSON.parse(readFileSync(here('./ssp-ch4-feedback.json'), 'utf8'));
const fixtures = JSON.parse(readFileSync(here('./validation_fixtures.json'), 'utf8'));

// 1e-6 is the meaningful floor, not 1e-9: numpy's vectorised RK4 and the
// scalar JS loop accumulate float64 round-off in a different order over ~4000
// steps. Observed worst case is ~7e-8. Anything above 1e-6 is a real bug.
const REL_TOL = 1e-6;
let failures = 0, checks = 0;

function close(name, got, want, tol = REL_TOL) {
  checks++;
  const denom = Math.max(Math.abs(want), 1e-6);
  const rel = Math.abs(got - want) / denom;
  if (!(rel < tol)) {
    failures++;
    console.log(`  FAIL ${name}: got ${got} want ${want} (rel ${rel.toExponential(2)})`);
  }
  return rel;
}

// ---------------------------------------------------------------- fixtures --
console.log(`Replaying ${fixtures.cases.length} Python fixtures in JavaScript...`);
let worst = 0, worstName = '';
for (const c of fixtures.cases) {
  const p = {
    gammaWetland: c.params.gamma_wetland,
    ecs: c.params.ecs,
    sTemperature: c.params.s_temperature,
    startYear: c.start_year,
    endYear: c.end_year,
  };
  const r = run(bundle, c.scenario, p);
  const n = r.year.length;
  const i2050 = r.year.indexOf ? -1 : -1;
  let idx2050 = -1;
  for (let i = 0; i < n; i++) if (r.year[i] === 2050) { idx2050 = i; break; }
  const tag = `${c.scenario} g=${c.params.gamma_wetland} ecs=${c.params.ecs} sT=${c.params.s_temperature}`;
  const pairs = [
    ['ch4_2100', r.ch4[n - 1], c.expect.ch4_2100],
    ['temperature_2100', r.temperature[n - 1], c.expect.temperature_2100],
    ['forcing_2100', r.forcing[n - 1], c.expect.forcing_2100],
    ['tau_2100', r.tau[n - 1], c.expect.tau_2100],
    ['ch4_2050', r.ch4[idx2050], c.expect.ch4_2050],
    ['temperature_2050', r.temperature[idx2050], c.expect.temperature_2050],
  ];
  for (const [k, got, want] of pairs) {
    const rel = close(`${tag} ${k}`, got, want);
    if (rel > worst) { worst = rel; worstName = `${tag} ${k}`; }
  }
}
console.log(`  worst relative difference: ${worst.toExponential(2)} (${worstName})`);

// -------------------------------------------------------------- invariants --
console.log('\nInvariants:');

function invariant(name, ok, detail = '') {
  checks++;
  if (!ok) { failures++; console.log(`  FAIL ${name} ${detail}`); }
  else console.log(`  pass ${name}${detail ? '  -> ' + detail : ''}`);
}

// 1. Mass balance, tested by INTEGRATION rather than differentiation:
//    B(t1) - B(t0) must equal the integral of (emissions - sink) dt. A central
//    difference on annual output would mostly measure its own truncation error
//    on a fast-changing pathway; Simpson's rule over 250 years does not.
{
  const r = run(bundle, 'ssp585', { startYear: 1850, endYear: 2100, substeps: 16 });
  const sc = bundle.scenarios.ssp585;
  const y0 = sc.year_start;
  const K = CONST.ppbToTg;
  const n = r.year.length;
  const net = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    net[i] = sc.ch4_emissions[Math.round(r.year[i] - y0)] + r.eNatural[i] - r.sink[i];
  }
  // composite Simpson over an even number of intervals
  const mEven = (n - 1) % 2 === 0 ? n - 1 : n - 2;
  let integral = net[0] + net[mEven];
  for (let i = 1; i < mEven; i++) integral += net[i] * (i % 2 ? 4 : 2);
  integral /= 3;
  const dBurden = (r.ch4[mEven] - r.ch4[0]) * K;
  const rel = Math.abs(integral - dBurden) / Math.abs(dBurden);
  invariant('CH4 mass balance closes (integral form)', rel < 2e-3,
    `d(burden) ${dBurden.toFixed(1)} Tg vs integral ${integral.toFixed(1)} Tg ` +
    `(rel ${rel.toExponential(2)})`);

  let maxSink = 0;
  for (let i = 0; i < n; i++) {
    maxSink = Math.max(maxSink, Math.abs(r.sink[i] - (r.ch4[i] * K) / r.tau[i]));
  }
  invariant('sink equals burden/tau', maxSink < 1e-9,
    `max deviation ${maxSink.toExponential(2)} Tg/yr`);
}

// 2. Integrator convergence: substeps must not change the answer.
{
  const a = run(bundle, 'ssp585', { startYear: 1850, endYear: 2100, substeps: 4 });
  const b = run(bundle, 'ssp585', { startYear: 1850, endYear: 2100, substeps: 32 });
  const d = Math.abs(a.ch4[a.ch4.length - 1] - b.ch4[b.ch4.length - 1]);
  const dT = Math.abs(a.temperature[a.year.length - 1] - b.temperature[b.year.length - 1]);
  invariant('insensitive to substep count', d < 0.02 && dT < 1e-4,
    `dCH4 ${d.toExponential(2)} ppb, dT ${dT.toExponential(2)} K`);
}

// 3. The loop must be POSITIVE: more feedback means more CH4 and more warming.
{
  let monotone = true;
  let prevCh4 = -Infinity, prevT = -Infinity;
  for (const g of [0, 10, 20, 30, 40]) {
    const r = run(bundle, 'ssp245', { gammaWetland: g, startYear: 1850, endYear: 2100 });
    const ch4 = r.ch4[r.ch4.length - 1], T = r.temperature[r.year.length - 1];
    if (ch4 < prevCh4 || T < prevT) monotone = false;
    prevCh4 = ch4; prevT = T;
  }
  invariant('monotone in feedback strength', monotone,
    'gamma 0 -> 40 raises both CH4 and temperature');
}

// 4. The loop must be DAMPED, not runaway: amplification is finite and modest.
{
  const d = runDecomposed(bundle, 'ssp585', {
    gammaWetland: 40, startYear: 1850, endYear: 2100,
  });
  const amp = d.amplification;
  invariant('loop is damped, not runaway', amp > 1 && amp < 1.3,
    `amplification ${amp.toFixed(4)}x at the top of the AR6 feedback range`);
}

// 5. The lifetime temperature sensitivity must OPPOSE the wetland feedback.
{
  const withDamp = run(bundle, 'ssp585', {
    gammaWetland: 20, sTemperature: -0.0408, startYear: 1850, endYear: 2100 });
  const noDamp = run(bundle, 'ssp585', {
    gammaWetland: 20, sTemperature: 0, startYear: 1850, endYear: 2100 });
  const a = withDamp.ch4[withDamp.ch4.length - 1];
  const b = noDamp.ch4[noDamp.ch4.length - 1];
  invariant('lifetime feedback damps the loop', a < b,
    `CH4 2100: ${a.toFixed(0)} ppb with damping vs ${b.toFixed(0)} without`);
}

// 6. AR6 anchors reproduced through the JS path.
{
  const r = run(bundle, 'ssp245', { gammaWetland: 0, startYear: 1750, endYear: 2100 });
  const { temperature } = rebaseTemperature(r, 1850, 1900);
  let sum = 0, k = 0;
  for (let i = 0; i < r.year.length; i++) {
    if (r.year[i] >= 2011 && r.year[i] <= 2020) { sum += temperature[i]; k++; }
  }
  const warming = sum / k;
  invariant('2011-2020 warming near AR6 observed 1.09 K',
    Math.abs(warming - 1.09) < 0.15, `${warming.toFixed(3)} K`);

  const cp = climateParams({});
  invariant('ECS/TCR match AR6 best estimates',
    Math.abs(cp.ecs - 3.0) < 1e-9 && Math.abs(cp.tcr - 1.8) < 0.01,
    `ECS ${cp.ecs.toFixed(2)} K, TCR ${cp.tcr.toFixed(2)} K`);
}

// 7. The default feedback strength must sit inside AR6's assessed range.
{
  const f = feedbackWm2PerK({});
  invariant('default gamma inside AR6 0.02-0.09 W m-2 K-1',
    f > 0.02 && f < 0.09, `${f.toFixed(4)} W m-2 K-1`);
}

// 8. The scenario list must be complete and carry skill scores.
{
  const list = listScenarios(bundle);
  invariant('scenario list complete with skill scores',
    list.length === 8 && list.every(s => s.label && s.ch4_rmse_ppb !== undefined),
    `${list.length} scenarios`);
}

// 9. Performance: fast enough to recompute on a slider drag.
{
  run(bundle, 'ssp245', { startYear: 1850, endYear: 2100 });  // warm up
  const t0 = performance.now();
  const N = 50;
  for (let i = 0; i < N; i++) {
    run(bundle, 'ssp245', { gammaWetland: i, startYear: 1850, endYear: 2100 });
  }
  const per = (performance.now() - t0) / N;
  invariant('fast enough for live interaction', per < 10,
    `${per.toFixed(2)} ms per 250-year run`);
}

console.log(`\n${checks - failures}/${checks} checks passed`);
if (failures) { console.error(`${failures} FAILURES`); process.exit(1); }
console.log('JavaScript matches the Python reference.');
