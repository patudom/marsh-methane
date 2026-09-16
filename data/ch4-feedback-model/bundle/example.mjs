#!/usr/bin/env node
/**
 * example.mjs - run the model from Node and print a small table.
 *
 *   node example.mjs                       # SSP2-4.5, gamma = 20
 *   node example.mjs ssp585 30             # scenario, feedback strength
 *   node example.mjs ssp370 20 --csv       # CSV to stdout instead
 *
 * Note the file is read with readFileSync, not fetch(): Node has a global
 * fetch, but it does not implement the file: scheme, so the browser-style
 * `await (await fetch('./x.json')).json()` fails there. Bundle the JSON, serve
 * it over HTTP, or read it from disk as below.
 */
import { readFileSync } from 'node:fs';
import {
  run, runDecomposed, rebaseTemperature, listScenarios, feedbackWm2PerK,
} from './ch4feedback.js';

const [slug = 'ssp245', gammaArg = '20', ...flags] = process.argv.slice(2);
const gammaWetland = Number(gammaArg);
const asCsv = flags.includes('--csv');

const bundle = JSON.parse(
  readFileSync(new URL('./ssp-ch4-feedback.json', import.meta.url), 'utf8'),
);

if (!bundle.scenarios[slug]) {
  console.error(`unknown scenario '${slug}'. Available:`);
  for (const s of listScenarios(bundle)) {
    console.error(`  ${s.slug.padEnd(14)} ${s.label.padEnd(15)} ` +
      `CH4 RMSE ${String(s.ch4_rmse_ppb).padStart(5)} ppb` +
      (s.calibration_scenario ? '  (calibration scenario)' : ''));
  }
  process.exit(1);
}

const opts = { gammaWetland, startYear: 1750, endYear: 2100 };
const d = runDecomposed(bundle, slug, opts);
const on = rebaseTemperature(d.withFeedback, 1850, 1900).temperature;
const off = rebaseTemperature(d.withoutFeedback, 1850, 1900).temperature;
const yrs = d.withFeedback.year;
const idx = (y) => { for (let i = 0; i < yrs.length; i++) if (yrs[i] === y) return i; return -1; };

if (asCsv) {
  console.log('year,ch4_ppb,ch4_no_feedback_ppb,ch4_cmip6_ppb,temp_K,temp_no_feedback_K,forcing_W_m2,tau_yr');
  for (let i = 0; i < yrs.length; i++) {
    console.log([
      yrs[i], d.withFeedback.ch4[i].toFixed(2), d.withoutFeedback.ch4[i].toFixed(2),
      d.withFeedback.ch4Cmip6[i].toFixed(2), on[i].toFixed(4), off[i].toFixed(4),
      d.withFeedback.forcing[i].toFixed(4), d.withFeedback.tau[i].toFixed(3),
    ].join(','));
  }
  process.exit(0);
}

console.log(`\n${bundle.scenarios[slug].label}   `
  + `gammaWetland = ${gammaWetland} Tg CH4/yr/K `
  + `(= ${feedbackWm2PerK(opts).toFixed(3)} W m-2 K-1; `
  + `AR6 assesses 0.02-0.09, low confidence)\n`);
console.log('           CH4 (ppb)                        temperature (K, vs 1850-1900)');
console.log('  year   loop on  loop off   CMIP6      loop on  loop off   loop adds');
console.log('  ' + '-'.repeat(72));
for (const y of [2000, 2020, 2040, 2060, 2080, 2100]) {
  const i = idx(y);
  if (i < 0) continue;
  console.log(`  ${y}  ${d.withFeedback.ch4[i].toFixed(0).padStart(7)}`
    + `  ${d.withoutFeedback.ch4[i].toFixed(0).padStart(8)}`
    + `  ${d.withFeedback.ch4Cmip6[i].toFixed(0).padStart(7)}`
    + `      ${on[i].toFixed(2).padStart(7)}  ${off[i].toFixed(2).padStart(8)}`
    + `  ${('+' + d.deltaTemperature[i].toFixed(3)).padStart(10)}`);
}
const n = yrs.length - 1;
console.log(`\n  By 2100 the loop itself adds `
  + `${d.finalDeltaCh4.toFixed(0)} ppb of CH4 and `
  + `${d.finalDeltaTemperature.toFixed(3)} K of warming `
  + `(amplification ${d.amplification.toFixed(3)}x).`);
console.log(`  CH4 lifetime ${d.withFeedback.tau[n].toFixed(2)} yr, `
  + `total forcing ${d.withFeedback.forcing[n].toFixed(2)} W m-2, `
  + `natural source ${d.withFeedback.eNatural[n].toFixed(0)} Tg/yr.\n`);
