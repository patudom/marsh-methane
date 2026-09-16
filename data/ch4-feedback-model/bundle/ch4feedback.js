/**
 * ch4feedback.js - coupled methane/temperature feedback model for the browser.
 *
 *   temperature -> natural CH4 emissions -> CH4 burden -> forcing -> temperature
 *
 * Dependency-free ES module. A 250-year run takes a few milliseconds, so a
 * dashboard can recompute on every slider drag rather than interpolating a
 * precomputed grid.
 *
 * This is a port of ch4feedback.py and is validated against it by
 * validate.mjs (fixed-step RK4 in both, so they agree to ~1e-9).
 *
 * THE TWO LEGS OF THE LOOP
 *   positive  gammaWetland  warming raises wetland/permafrost CH4 emissions.
 *                           AR6 assesses the combined non-CO2 biogeochemical
 *                           feedback at 0.02-0.09 W m-2 degC-1, LOW confidence
 *                           - roughly 7-30 Tg CH4 yr-1 K-1 here. There is no
 *                           defensible single value; put it on a slider.
 *   negative  sTemperature  warming means more water vapour, more OH, and a
 *                           shorter CH4 lifetime (-0.0408 per K), plus the
 *                           ozone forcing temperature feedback. The loop is
 *                           DAMPED. It does not run away.
 *
 * Usage
 *   import { run, runDecomposed, DEFAULTS, listScenarios } from './ch4feedback.js';
 *   const bundle = await (await fetch('./ssp-ch4-feedback.json')).json();
 *   const out = run(bundle, 'ssp245', { gammaWetland: 20, ecs: 3 });
 *   // out.year, out.ch4, out.temperature, out.forcing, out.tau, ...
 */

// --------------------------------------------------------------------------
// Constants (mirrors of the Python module; the bundle also carries them)
// --------------------------------------------------------------------------

const MASS_ATMOSPHERE = 5.1352e18;   // kg dry air
const MW_AIR = 28.97;                // g/mol
const MW_CH4 = 16.043;               // g/mol

export const CONST = {
  // Derived, never hardcoded: a value rounded to 7 figures here drifts from the
  // Python reference by ~1e-5 and shows up as spurious validation failures.
  ppbToTg: (MASS_ATMOSPHERE * (MW_CH4 / MW_AIR) * 1e-9) / 1e9,
  ch4Base: 729.2,           // ppb, FaIR/AR6 1750 reference
  n2oBase: 270.1,           // ppb
  // Meinshausen et al. (2020) CH4 forcing coefficients
  a3: -8.9603e-5, b3: -1.2462e-4, d3: 0.045194,
  ch4TropAdj: -0.14,        // ERF/RF - 1 for CH4
  sCh4PerPpb: 2.54e-4,      // CH4 self-feedback on its own lifetime
  ozoneReCh4: 1.75e-4,      // W m-2 ppb-1
  h2oStratCh4: 4.4e-5,      // W m-2 ppb-1
  erfariReCh4: -2.0e-6,     // W m-2 ppb-1
};

/** Default parameters. Override any subset when calling run(). */
export const DEFAULTS = {
  // methane cycle
  tauBase: 10.878,          // calibrated; see bundle.calibration
  eNat: 155.676,            // calibrated natural CH4 emissions at T=0 [Tg/yr]
  sTemperature: -0.0408,    // dln(tau)/dT [1/K] - NEGATIVE, damps the loop
  // the positive leg
  gammaWetland: 20.0,       // Tg CH4 yr-1 K-1
  gammaPermafrost: 0.0,     // additional, if you want it as its own slider
  // two-layer energy balance
  ecs: 3.0,                 // equilibrium climate sensitivity [K]
  forcing2co2: 3.93,        // W m-2 (AR6 Ch.7)
  cSurface: 7.3,            // W yr m-2 K-1
  cDeep: 106.0,             // W yr m-2 K-1
  kappa: 0.677,             // W m-2 K-1
  epsilon: 1.29,            // deep-ocean heat uptake efficacy
  // other
  ozoneTempFeedback: -0.037, // W m-2 K-1
  forcingScale: 1.0,        // scale non-CH4 forcing (sensitivity tests)
  // integration / window
  startYear: null,          // null = the scenario's first year
  endYear: null,            // null = the scenario's last year
  substeps: 4,              // RK4 steps per year; must match the Python to validate
  c0: null,                 // initial CH4 [ppb]; null = prescribed CMIP6 value
};

// --------------------------------------------------------------------------
// Forcing
// --------------------------------------------------------------------------

/** CH4 ERF [W m-2] relative to 1750. Meinshausen et al. (2020). */
export function erfCh4(ch4, n2o) {
  const { a3, b3, d3, ch4Base, ch4TropAdj } = CONST;
  return (a3 * Math.sqrt(ch4) + b3 * Math.sqrt(n2o) + d3)
    * (Math.sqrt(ch4) - Math.sqrt(ch4Base)) * (1 + ch4TropAdj);
}

/** CH4's non-greenhouse terms: tropospheric ozone, stratospheric H2O, aerosols. */
export function erfCh4Extras(ch4) {
  const { ch4Base, ozoneReCh4, h2oStratCh4, erfariReCh4 } = CONST;
  return (ch4 - ch4Base) * (ozoneReCh4 + h2oStratCh4 + erfariReCh4);
}

/**
 * gammaTotal expressed as W m-2 K-1, so a UI can show where a slider position
 * sits relative to AR6's assessed 0.02-0.09 W m-2 degC-1.
 */
export function feedbackWm2PerK(params = {}, ch4 = 1900, n2o = 332) {
  const p = { ...DEFAULTS, ...params };
  const gamma = p.gammaWetland + p.gammaPermafrost;
  const dppb = (gamma * p.tauBase) / CONST.ppbToTg;
  const slope = (erfCh4(ch4 + 0.5, n2o) - erfCh4(ch4 - 0.5, n2o))
    + (erfCh4Extras(ch4 + 0.5) - erfCh4Extras(ch4 - 0.5));
  return dppb * slope;
}

/** snake_case keys in the JSON bundle -> camelCase parameter names. */
const KEY_MAP = {
  tau_base: 'tauBase', e_nat: 'eNat', s_temperature: 'sTemperature',
  gamma_wetland: 'gammaWetland', gamma_permafrost: 'gammaPermafrost',
  ecs: 'ecs', forcing_2co2: 'forcing2co2', c_surface: 'cSurface',
  c_deep: 'cDeep', kappa: 'kappa', epsilon: 'epsilon',
  ozone_temp_feedback: 'ozoneTempFeedback', forcing_scale: 'forcingScale',
};

/**
 * The bundle's own calibrated defaults, as camelCase params. Prefer these over
 * the hardcoded DEFAULTS so a re-calibrated bundle takes effect without
 * touching this file.
 */
export function paramsFromBundle(bundle) {
  const out = {};
  for (const [k, v] of Object.entries(bundle.defaults ?? {})) {
    if (KEY_MAP[k] !== undefined) out[KEY_MAP[k]] = v;
  }
  return out;
}

/** Diagnostics implied by the energy-balance parameters. */
export function climateParams(params = {}) {
  const p = { ...DEFAULTS, ...params };
  const lambda = p.forcing2co2 / p.ecs;
  return { lambda, ecs: p.ecs, tcr: p.forcing2co2 / (lambda + p.epsilon * p.kappa) };
}

// --------------------------------------------------------------------------
// Integration
// --------------------------------------------------------------------------

/** Linear interpolation with end-clamping. Matches numpy.interp. */
function interp(x, xs, ys) {
  const n = xs.length;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid; else hi = mid;
  }
  const t = (x - xs[lo]) / (xs[hi] - xs[lo]);
  return ys[lo] + t * (ys[hi] - ys[lo]);
}

/**
 * Right-hand side of the coupled system.
 * y = [burden (Tg CH4), T surface (K), T deep (K)]
 */
function rhs(t, y, p, sc, lambda) {
  const burden = Math.max(y[0], 1e-9);
  const temp = y[1], tempDeep = y[2];
  const ch4 = burden / CONST.ppbToTg;

  const eAnth = interp(t, sc.year, sc.ch4_emissions);
  const n2o = interp(t, sc.year, sc.n2o);
  const fOther = interp(t, sc.year, sc.f_other);
  const alphaExt = interp(t, sc.year, sc.alpha_chem_ext);

  // CH4 lifetime: external chemistry x CH4 self-feedback x temperature
  let alpha = alphaExt
    * (1 + (ch4 - CONST.ch4Base) * CONST.sCh4PerPpb)
    * (1 + temp * p.sTemperature);
  if (alpha < 0.05) alpha = 0.05;
  const tau = p.tauBase * alpha;

  // methane budget, including the warming-driven natural source
  const eNatural = p.eNat + (p.gammaWetland + p.gammaPermafrost) * temp;
  const dBurden = eAnth + eNatural - burden / tau;

  // total effective radiative forcing
  const forcing = p.forcingScale * fOther
    + erfCh4(ch4, n2o) + erfCh4Extras(ch4)
    + p.ozoneTempFeedback * temp;

  // two-layer energy balance
  const dTemp = (forcing - lambda * temp
    - p.epsilon * p.kappa * (temp - tempDeep)) / p.cSurface;
  const dDeep = (p.kappa * (temp - tempDeep)) / p.cDeep;

  return { d: [dBurden, dTemp, dDeep], tau, forcing, ch4, eNatural };
}

/**
 * Integrate the coupled model.
 *
 * @param {object} bundle  parsed ssp-ch4-feedback.json
 * @param {string} slug    e.g. 'ssp245'
 * @param {object} params  any subset of DEFAULTS
 * @returns {object} arrays: year, ch4, tau, forcing, temperature,
 *   temperatureDeep, eNatural, sink, ch4Cmip6 - plus `params` and `climate`.
 */
export function run(bundle, slug, params = {}) {
  const p = { ...DEFAULTS, ...paramsFromBundle(bundle), ...params };
  const raw = bundle.scenarios[slug];
  if (!raw) throw new Error(`unknown scenario '${slug}'`);

  // rebuild the year axis once (the JSON stores only its start, to stay small)
  const n0 = raw.ch4_emissions.length;
  const year = new Float64Array(n0);
  for (let i = 0; i < n0; i++) year[i] = raw.year_start + i;
  const sc = { ...raw, year };

  const startYear = p.startYear ?? year[0];
  const endYear = p.endYear ?? year[n0 - 1];
  const i0 = Math.round(startYear - year[0]);
  const i1 = Math.round(endYear - year[0]);
  if (i0 < 0 || i1 >= n0 || i1 <= i0) {
    throw new Error(`window ${startYear}-${endYear} outside ${year[0]}-${year[n0 - 1]}`);
  }

  const lambda = p.forcing2co2 / p.ecs;

  let c0 = p.c0;
  if (c0 === null || c0 === undefined) {
    c0 = interp(startYear, year, sc.ch4_cmip6);
  } else if (c0 === 'steady') {
    const e0 = interp(startYear, year, sc.ch4_emissions);
    const a0 = interp(startYear, year, sc.alpha_chem_ext);
    c0 = 700;
    for (let k = 0; k < 60; k++) {
      const a = a0 * (1 + (c0 - CONST.ch4Base) * CONST.sCh4PerPpb);
      c0 = ((e0 + p.eNat) * p.tauBase * a) / CONST.ppbToTg;
    }
  }

  let y = [c0 * CONST.ppbToTg, 0, 0];
  const n = i1 - i0 + 1;
  const out = {
    year: new Float64Array(n), ch4: new Float64Array(n),
    tau: new Float64Array(n), forcing: new Float64Array(n),
    temperature: new Float64Array(n), temperatureDeep: new Float64Array(n),
    eNatural: new Float64Array(n), sink: new Float64Array(n),
    ch4Cmip6: new Float64Array(n),
  };
  const h = 1 / p.substeps;

  for (let k = 0; k < n; k++) {
    let t = year[i0 + k];
    const s = rhs(t, y, p, sc, lambda);
    out.year[k] = t;
    out.ch4[k] = s.ch4;
    out.tau[k] = s.tau;
    out.forcing[k] = s.forcing;
    out.temperature[k] = y[1];
    out.temperatureDeep[k] = y[2];
    out.eNatural[k] = s.eNatural;
    out.sink[k] = y[0] / s.tau;
    out.ch4Cmip6[k] = sc.ch4_cmip6[i0 + k];
    if (k === n - 1) break;

    for (let j = 0; j < p.substeps; j++) {
      const k1 = rhs(t, y, p, sc, lambda).d;
      const y2 = [y[0] + (h / 2) * k1[0], y[1] + (h / 2) * k1[1], y[2] + (h / 2) * k1[2]];
      const k2 = rhs(t + h / 2, y2, p, sc, lambda).d;
      const y3 = [y[0] + (h / 2) * k2[0], y[1] + (h / 2) * k2[1], y[2] + (h / 2) * k2[2]];
      const k3 = rhs(t + h / 2, y3, p, sc, lambda).d;
      const y4 = [y[0] + h * k3[0], y[1] + h * k3[1], y[2] + h * k3[2]];
      const k4 = rhs(t + h, y4, p, sc, lambda).d;
      y = [
        y[0] + (h / 6) * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
        y[1] + (h / 6) * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
        y[2] + (h / 6) * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
      ];
      t += h;
    }
  }

  out.params = p;
  out.climate = climateParams(p);
  out.feedbackWm2PerK = feedbackWm2PerK(p);
  return out;
}

/**
 * Run twice - loop on, loop off - and difference. This is the headline pair of
 * numbers for a feedback dashboard: how much extra methane, and how much extra
 * warming, the loop itself is responsible for.
 */
export function runDecomposed(bundle, slug, params = {}) {
  const on = run(bundle, slug, params);
  const off = run(bundle, slug, { ...params, gammaWetland: 0, gammaPermafrost: 0 });
  const n = on.year.length;
  const dCh4 = new Float64Array(n), dTemp = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    dCh4[i] = on.ch4[i] - off.ch4[i];
    dTemp[i] = on.temperature[i] - off.temperature[i];
  }
  return {
    withFeedback: on,
    withoutFeedback: off,
    deltaCh4: dCh4,
    deltaTemperature: dTemp,
    finalDeltaCh4: dCh4[n - 1],
    finalDeltaTemperature: dTemp[n - 1],
    amplification: off.temperature[n - 1] !== 0
      ? on.temperature[n - 1] / off.temperature[n - 1] : NaN,
  };
}

/**
 * Re-express temperature as an anomaly against a baseline period, the way
 * IPCC figures do (1850-1900). The raw model zero is the 1750 state.
 */
export function rebaseTemperature(result, baseStart = 1850, baseEnd = 1900) {
  let sum = 0, count = 0;
  for (let i = 0; i < result.year.length; i++) {
    if (result.year[i] >= baseStart && result.year[i] <= baseEnd) {
      sum += result.temperature[i]; count++;
    }
  }
  if (!count) return { offset: 0, temperature: result.temperature };
  const offset = sum / count;
  const out = new Float64Array(result.year.length);
  for (let i = 0; i < out.length; i++) out[i] = result.temperature[i] - offset;
  return { offset, temperature: out };
}

/** Scenario list with labels and the skill scores, for building a picker. */
export function listScenarios(bundle) {
  return Object.entries(bundle.scenarios).map(([slug, s]) => ({
    slug,
    label: s.label,
    ...(bundle.calibration?.skill_by_scenario?.[slug] ?? {}),
  }));
}

/** Convenience: rows ready for a charting library. */
export function toRows(result, { rebase = true } = {}) {
  const temp = rebase ? rebaseTemperature(result).temperature : result.temperature;
  const rows = [];
  for (let i = 0; i < result.year.length; i++) {
    rows.push({
      year: result.year[i],
      ch4: result.ch4[i],
      ch4Cmip6: result.ch4Cmip6[i],
      temperature: temp[i],
      forcing: result.forcing[i],
      tau: result.tau[i],
      naturalEmissions: result.eNatural[i],
    });
  }
  return rows;
}
