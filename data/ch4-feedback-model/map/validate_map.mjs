/**
 * validate_map.mjs - checks for ch4map.js, including end-to-end composition
 * with ch4feedback.js.
 *
 *   node validate_map.mjs
 */
import { readFileSync } from 'node:fs';
// Paths relative to THIS file, so the harness runs from any directory.
const here = (rel) => new URL(rel, import.meta.url);
import { run, runDecomposed } from '../bundle/ch4feedback.js';
import { createMapper, DEFAULT_BASELINE } from './ch4map.js';

// Node has no ImageData; a minimal stand-in so toImageData is testable here.
if (typeof globalThis.ImageData === 'undefined') {
  globalThis.ImageData = class ImageData {
    constructor(data, width, height) {
      Object.assign(this, { data, width, height: height ?? data.length / 4 / width });
    }
  };
}

const pat = JSON.parse(readFileSync(here('./conus-pattern.json'), 'utf8'));
const fb = JSON.parse(readFileSync(here('../bundle/ssp-ch4-feedback.json'), 'utf8'));
const map = createMapper(pat);

let checks = 0, failures = 0;
function ok(name, pass, detail = '') {
  checks++;
  if (pass) console.log(`  pass ${name}${detail ? '  -> ' + detail : ''}`);
  else { failures++; console.log(`  FAIL ${name}  ${detail}`); }
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

console.log('Pattern integrity:');
{
  const nodata = pat.meta.nodata;
  ok('no nodata sentinel leaks into the field',
    !Array.from(map.pattern).some((v) => v === nodata),
    `${Array.from(map.pattern).filter(Number.isNaN).length} NaN cells (off-land)`);

  let wsum = 0, vsum = 0;
  for (let i = 0; i < map.pattern.length; i++) {
    if (Number.isFinite(map.pattern[i])) {
      vsum += map.pattern[i] * map.weight[i]; wsum += map.weight[i];
    }
  }
  const mean = vsum / wsum;
  ok('area-weighted mean matches the bundle',
    near(mean, pat.calibration.area_weighted_mean, 1e-3),
    `${mean.toFixed(4)} vs ${pat.calibration.area_weighted_mean}`);

  ok('pattern magnitudes are physically plausible',
    pat.calibration.min > 0.5 && pat.calibration.max < 2.5 && mean > 1.0,
    `[${pat.calibration.min}, ${pat.calibration.max}], mean ${mean.toFixed(2)} ` +
    `(land warms faster than the global mean, so mean > 1 is required)`);

  ok('synthetic pattern is flagged as synthetic', map.isSynthetic === true,
    'meta.synthetic true, so a UI can say so');
}

console.log('\nPattern scaling:');
{
  const a = map.fieldFromDelta(1.0);
  const b = map.fieldFromDelta(2.0);
  let maxRel = 0;
  for (let i = 0; i < a.values.length; i++) {
    if (!Number.isFinite(a.values[i])) continue;
    maxRel = Math.max(maxRel, Math.abs(b.values[i] - 2 * a.values[i]) /
      Math.abs(2 * a.values[i]));
  }
  ok('linear in the global anomaly', maxRel < 1e-6,
    `max relative deviation ${maxRel.toExponential(2)}`);

  const z = map.fieldFromDelta(0);
  ok('zero global anomaly gives a zero field',
    Array.from(z.values).every((v) => !Number.isFinite(v) || v === 0));

  const neg = map.fieldFromDelta(-0.5);
  ok('handles cooling (needed for overshoot scenarios)',
    neg.max < 0 && neg.min < neg.max,
    `range ${neg.min.toFixed(3)} to ${neg.max.toFixed(3)} K`);
}

console.log('\nBaseline rebasing:');
{
  const r = run(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
  const base = map.baselineMean(r, DEFAULT_BASELINE);

  // exactness: P*(G(t)-G(base)) must equal the field, since subtraction
  // commutes with the multiply
  const f = map.field(r, 2075);
  let gi = -1;
  for (let i = 0; i < r.year.length; i++) if (r.year[i] === 2075) gi = i;
  const expect = r.temperature[gi] - base;
  ok('field delta equals global anomaly minus baseline mean',
    near(f.globalDelta, expect, 1e-12),
    `${f.globalDelta.toFixed(6)} K`);

  let maxErr = 0;
  for (let i = 0; i < f.values.length; i++) {
    if (!Number.isFinite(f.values[i])) continue;
    maxErr = Math.max(maxErr, Math.abs(f.values[i] - map.pattern[i] * expect));
  }
  ok('rebasing is exact, not approximate', maxErr < 1e-6,
    `max error ${maxErr.toExponential(2)} K`);

  // a year inside the baseline window should be near zero
  const mid = map.field(r, 2005);
  ok('mid-baseline year is near zero', Math.abs(mid.mean) < 0.25,
    `CONUS mean ${mid.mean.toFixed(3)} K in 2005 vs a 1995-2014 baseline`);

  ok('rejects a baseline outside the run',
    (() => { try { map.field(r, 2075, { baseline: [1700, 1750] }); return false; }
             catch { return true; } })());
  ok('rejects a year outside the run',
    (() => { try { map.field(r, 2500); return false; } catch { return true; } })());
}

console.log('\nSampling:');
{
  const f = map.fieldFromDelta(2.0);
  const { lat, lon, nlon } = map.grid;
  // exact at a grid node
  const j = 20, i = 40;
  const gridVal = f.values[j * nlon + i];
  ok('sample is exact at a grid node',
    near(map.sample(f, lat[j], lon[i]), gridVal, 1e-5),
    `${map.sample(f, lat[j], lon[i]).toFixed(6)} vs ${gridVal.toFixed(6)}`);

  // bilinear midpoint equals the mean of the four surrounding cells
  const half = map.grid.step / 2;
  const v = [f.values[j * nlon + i], f.values[j * nlon + i + 1],
    f.values[(j + 1) * nlon + i], f.values[(j + 1) * nlon + i + 1]];
  if (v.every(Number.isFinite)) {
    const avg = v.reduce((a, b) => a + b) / 4;
    ok('bilinear midpoint equals the 4-cell mean',
      near(map.sample(f, lat[j] + half, lon[i] + half), avg, 1e-5),
      `${map.sample(f, lat[j] + half, lon[i] + half).toFixed(6)} vs ${avg.toFixed(6)}`);
  }

  ok('offshore returns NaN', !Number.isFinite(map.sample(f, 30.0, -75.0)),
    'Atlantic off Florida');
  ok('outside the window returns NaN', !Number.isFinite(map.sample(f, 60, -100)));

  // known cities: interior must exceed coastal at the same global warming
  const denver = map.sample(f, 39.7, -105.0);
  const sf = map.sample(f, 37.8, -122.4);
  const fargo = map.sample(f, 46.9, -96.8);
  const miami = map.sample(f, 25.8, -80.2);
  ok('interior warms more than the Pacific coast', denver > sf + 0.3,
    `Denver ${denver.toFixed(2)} K vs San Francisco ${sf.toFixed(2)} K`);
  ok('north warms more than south', fargo > miami + 0.5,
    `Fargo ${fargo.toFixed(2)} K vs Miami ${miami.toFixed(2)} K`);
}

console.log('\nPer-state means:');
{
  const f = map.fieldFromDelta(2.0);
  const sm = map.stateMeans(f).filter((s) => Number.isFinite(s.value));
  ok('every state gets a value', sm.length === pat.state_names.length,
    `${sm.length}/${pat.state_names.length}`);
  const sorted = [...sm].sort((a, b) => b.value - a.value);
  ok('state ordering is physically sensible',
    ['North Dakota', 'Minnesota', 'Montana', 'Wisconsin', 'South Dakota']
      .includes(sorted[0].name) && sorted[sorted.length - 1].name === 'Florida',
    `warmest ${sorted[0].name} ${sorted[0].value.toFixed(2)}, ` +
    `coolest ${sorted[sorted.length - 1].name} ${sorted[sorted.length - 1].value.toFixed(2)}`);
  const lo = Math.min(...sm.map((s) => s.value));
  const hi = Math.max(...sm.map((s) => s.value));
  ok('state means lie inside the grid range', lo >= f.min - 1e-9 && hi <= f.max + 1e-9,
    `[${lo.toFixed(3)}, ${hi.toFixed(3)}] inside [${f.min.toFixed(3)}, ${f.max.toFixed(3)}]`);
}

console.log('\nColour scale:');
{
  ok('ramp lightness is monotone per arm',
    pat.ramp.check.monotone_cool && pat.ramp.check.monotone_warm,
    `arm asymmetry ${pat.ramp.check.max_arm_asymmetry_L}`);
  ok('arms are perceptually balanced',
    pat.ramp.check.max_arm_asymmetry_L < 0.01,
    'neither side of the diverging scale reads heavier');
  ok('a sequential ramp is provided', Array.isArray(pat.ramp.sequential)
    && pat.ramp.sequential.length >= 5, `${pat.ramp.sequential?.length} steps`);

  // an all-positive field must get a SEQUENTIAL scale
  const warm = map.fieldFromDelta(2.0);
  const s1 = map.chooseScale(warm);
  ok('all-positive field gets a sequential scale from 0',
    s1.kind === 'sequential' && s1.lo === 0 && s1.hi >= warm.max,
    `${s1.kind} [${s1.lo}, ${s1.hi}] for a field in ` +
    `[${warm.min.toFixed(2)}, ${warm.max.toFixed(2)}] ` +
    `(a diverging scale here would waste half its range)`);

  // A signed field must get a SYMMETRIC diverging scale. Note SSP1-1.9 does
  // NOT provide one: it peaks and declines, but stays above the 1995-2014
  // level through 2100, so it is still all-positive. A year BEFORE the
  // baseline is the case that genuinely goes negative.
  const r119 = run(fb, 'ssp119', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
  const peak119 = map.field(r119, 2060), end119 = map.field(r119, 2100);
  ok('overshoot scenario peaks then declines but stays above the baseline',
    end119.mean < peak119.mean && end119.min > 0,
    `SSP1-1.9 CONUS mean ${peak119.mean.toFixed(2)} K in 2060 -> ` +
    `${end119.mean.toFixed(2)} K in 2100, still positive vs 1995-2014`);

  const past = map.field(r119, 1950);
  const s2 = map.chooseScale(past);
  ok('a pre-baseline year gives a negative field', past.max < 0,
    `1950 vs 1995-2014: [${past.min.toFixed(2)}, ${past.max.toFixed(2)}] K`);
  ok('signed field gets a symmetric diverging scale',
    s2.kind === 'diverging' && Math.abs(s2.lo + s2.hi) < 1e-9,
    `${s2.kind} [${s2.lo}, ${s2.hi}]`);
  const mid = map.colorFor(0, s2);
  const hex = '#' + mid.map((v) => v.toString(16).padStart(2, '0')).join('');
  ok('zero maps to the neutral midpoint on a diverging scale',
    hex.toLowerCase() === pat.ramp.midpoint_light.toLowerCase(),
    `${hex} (the midpoint must read as "no change")`);

  // a whole animation must share ONE scale
  const rr = run(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
  const frames = map.fieldSeries(rr, [2030, 2050, 2075, 2100]);
  const shared = map.chooseScale(frames);
  ok('one scale covers every frame of an animation',
    frames.every((f) => f.max <= shared.hi + 1e-9 && f.min >= shared.lo - 1e-9),
    `${shared.kind} [${shared.lo}, ${shared.hi}] covers ` +
    frames.map((f) => `${f.year}:${f.max.toFixed(2)}`).join(' '));

  // the encoding must be INVERTIBLE, or the map cannot be read off the legend
  const scale = map.chooseScale(warm);
  const probe = [0.2, 0.7, 1.4, 2.2, 2.8].filter((v) => v <= scale.hi);
  let worst = 0;
  for (const v of probe) {
    const rgb = map.colorFor(v, scale);
    // nearest-value search back through the scale
    let best = 0, bestD = Infinity;
    for (let k = 0; k <= 400; k++) {
      const cand = scale.lo + (scale.hi - scale.lo) * (k / 400);
      const c = map.colorFor(cand, scale);
      const d = (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2;
      if (d < bestD) { bestD = d; best = cand; }
    }
    worst = Math.max(worst, Math.abs(best - v));
  }
  ok('colour encoding is invertible', worst < 0.1,
    `max round-trip error ${worst.toFixed(3)} K - a reader can recover the ` +
    `value from the legend`);

  ok('saturates beyond the domain',
    JSON.stringify(map.colorFor(99, scale)) ===
    JSON.stringify(map.colorFor(scale.hi, scale)));
  ok('non-finite values get no colour', map.colorFor(NaN, scale) === null,
    'off-land cells stay transparent');
  ok('legend stops span the domain',
    (() => { const L = map.legendStops(scale); return L.length === 5
      && L[0].value === scale.lo && Math.abs(L[4].value - scale.hi) < 1e-9; })());
}

console.log('\nRendering:');
{
  const f = map.fieldFromDelta(2.0);
  const { imageData } = map.toImageData(f, { scale: map.chooseScale(f) });
  ok('ImageData matches the grid',
    imageData.width === map.grid.nlon && imageData.height === map.grid.nlat,
    `${imageData.width}x${imageData.height}`);
  const d = imageData.data;
  let opaque = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] === 255) opaque++;
  const land = Array.from(map.pattern).filter(Number.isFinite).length;
  ok('opaque pixels equal land cells', opaque === land, `${opaque} == ${land}`);

  // row 0 must be NORTH: the top row should be warmer than the bottom
  const nlon = map.grid.nlon, nlat = map.grid.nlat;
  const rowMean = (jRow) => {
    let s = 0, n = 0;
    for (let i = 0; i < nlon; i++) {
      const v = f.values[(nlat - 1 - jRow) * nlon + i];
      if (Number.isFinite(v)) { s += v; n++; }
    }
    return n ? s / n : NaN;
  };
  ok('row 0 of the image is north', rowMean(5) > rowMean(nlat - 6),
    `top rows ${rowMean(5).toFixed(2)} K > bottom rows ${rowMean(nlat - 6).toFixed(2)} K`);
}

console.log('\nProjection:');
{
  const p = map.makeProjection({ width: 900 });
  for (const [lo, la] of [[-100, 40], [-122.4, 37.8], [-80.2, 25.8]]) {
    const [x, y] = p.project(lo, la);
    const [lo2, la2] = p.unproject(x, y);
    ok(`round-trip ${lo},${la}`, near(lo, lo2, 1e-9) && near(la, la2, 1e-9));
  }
  const [xw] = p.project(-125, 38), [xe] = p.project(-66.5, 38);
  const [, yn] = p.project(-100, 49.5), [, ys] = p.project(-100, 24);
  ok('west is left and north is up', xw < xe && yn < ys);
  ok('aspect ratio is cos-latitude corrected',
    Math.abs((xe - xw) / (ys - yn) - 1.85) < 0.35,
    `${((xe - xw) / (ys - yn)).toFixed(2)} (CONUS is about 1.8:1 as drawn)`);
}

console.log('\nEnd-to-end with ch4feedback.js:');
{
  const years = [2030, 2050, 2075, 2100];
  for (const slug of ['ssp126', 'ssp245', 'ssp585']) {
    const r = run(fb, slug, { gammaWetland: 20, startYear: 1850, endYear: 2100 });
    const f = map.field(r, 2100);
    ok(`${slug} 2100 map is plausible`,
      f.mean > -1 && f.mean < 8 && f.max > f.min,
      `CONUS mean ${f.mean.toFixed(2)} K, range ${f.min.toFixed(2)} to ${f.max.toFixed(2)} K ` +
      `(global ${f.globalDelta.toFixed(2)} K)`);
  }

  // the loop's own contribution, spatialised
  const d = runDecomposed(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
  const lf = map.loopField(d, 2100);
  ok('loop field magnitude matches the 0-D model',
    near(lf.globalDelta, d.finalDeltaTemperature, 1e-12),
    `global +${lf.globalDelta.toFixed(4)} K -> CONUS mean +${lf.mean.toFixed(4)} K, ` +
    `peak +${lf.max.toFixed(4)} K`);
  ok('loop contribution is small but positive',
    lf.mean > 0.01 && lf.mean < 0.5,
    'needs its own colour scale; it would vanish on the total-warming scale');

  // monotone in time for a monotone scenario
  const r585 = run(fb, 'ssp585', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
  const series = map.fieldSeries(r585, years);
  ok('warming increases with year under SSP5-8.5',
    series.every((f, i) => i === 0 || f.mean > series[i - 1].mean),
    series.map((f) => `${f.year}: ${f.mean.toFixed(2)}`).join(', '));
}

console.log('\nPerformance:');
{
  const r = run(fb, 'ssp245', { startYear: 1850, endYear: 2100 });
  map.field(r, 2050);
  const t0 = performance.now();
  const N = 200;
  for (let i = 0; i < N; i++) map.field(r, 1900 + (i % 200));
  const per = (performance.now() - t0) / N;
  ok('fast enough for a year slider', per < 3,
    `${per.toFixed(3)} ms per field (${map.pattern.length} cells)`);
}

console.log(`\n${checks - failures}/${checks} checks passed`);
if (failures) { console.error(`${failures} FAILURES`); process.exit(1); }
console.log('ch4map.js is consistent and composes with ch4feedback.js.');
