# CONUS warming maps by pattern scaling

Turns the global temperature output of `../bundle/ch4feedback.js` into a map of
the contiguous United States — live in the browser, and as image sets for
WorldWide Telescope.

```
dT(x, y, t)  =  P(x, y) * [ dT_global(t) - dT_global(baseline) ]
```

`P` is dimensionless: local kelvin per global kelvin. Because the baseline
subtraction commutes with the multiply, rebasing to "warming since today" is
**exact**, not an approximation. A field is one multiply per grid cell (~3,300
of them), so a year slider regenerates the whole map in about 0.1 ms.

## ⚠ The bundled pattern is SYNTHETIC

It is **not** derived from CMIP6 output — ESGF was not reachable from the
environment this was built in. What *is* real: the land/ocean mask, the state
boundaries, and both distance fields, all computed from Natural Earth 1:50m
vectors. What is invented: the mapping from those fields to `P`.

It is built from three genuine physical drivers — latitude, distance to the
nearest ocean, and distance to ocean *looking west* (prevailing westerlies
carry Pacific marine air inland, which is why the west coast is far more
damped than the east) — and fitted to 13 anchor values chosen to be consistent
with published CMIP6 behaviour. Area-weighted CONUS mean `P` = **1.25**, range
0.89–1.43, anchor RMS 0.029.

`bundle.meta.synthetic` is `true` and `map.isSynthetic` exposes it. **Surface
that in your UI.** Run `derive_pattern_from_cmip6.py` to replace it with the
real thing; the JSON schema is identical, so nothing downstream changes.

## Files

| File | What it is |
|---|---|
| `ch4map.js` | The browser module. ES module, no dependencies. |
| `conus-pattern.json` | Pattern grid, land mask, per-cell state index, state outlines, colour ramps (166 KB). |
| `build_pattern.py` | Builds the synthetic pattern from Natural Earth vectors. |
| `export_bundle.py` | Pattern → `conus-pattern.json`. `--pattern real_pattern.npz` for CMIP6 output. |
| `derive_pattern_from_cmip6.py` | **The real-data path.** Per-gridcell regression from CMIP6 `tas`. |
| `test_ingest.py` | Verifies that script recovers a *known* pattern. Run before trusting it. |
| `export_wwt.py` | Renders WorldWide Telescope image sets (and plate carrée / KML / GIS). |
| `validate_map.mjs` | 49 checks on `ch4map.js`, including composition with the feedback model. |
| `validate_wwt.py` | 80 checks on the WWT export, including TOAST geometry. |
| `wwt/` | A generated 8-frame SSP2-4.5 export, ready to open. |
| `_conus.npy` | The CONUS land mask, reused by the CMIP6 ingest script. |

## Browser use

```js
import { run, runDecomposed } from '../bundle/ch4feedback.js';
import { createMapper } from './ch4map.js';

const [fb, pat] = await Promise.all([
  fetch('../bundle/ssp-ch4-feedback.json').then((r) => r.json()),
  fetch('./conus-pattern.json').then((r) => r.json()),
]);
const map = createMapper(pat);
const result = run(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });

// one frame, warming vs 1995-2014
const field = map.field(result, 2075);
field.values;        // Float64Array over the grid, NaN off-land
field.mean;          // area-weighted CONUS mean, K
field.globalDelta;   // the global anomaly that produced it

// ONE scale for every frame of an animation
const frames = map.fieldSeries(result, [2030, 2050, 2075, 2100]);
const scale = map.chooseScale(frames);
const { imageData } = map.toImageData(field, { scale });

// hover readouts
map.sample(field, 39.7, -105.0);   // bilinear, K, NaN offshore
map.stateMeans(field);             // [{name, value}] area-weighted, all 48

// the methane loop's own contribution, spatialised
const d = runDecomposed(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
map.loopField(d, 2100);            // ~+0.11 K CONUS mean - needs its own scale
```

Also exported: `rebaseTemperature`-style `baselineMean`, `fieldFromDelta`,
`colorFor`, `legendStops`, `makeProjection`, `drawOutlines`, `listScenarios`,
`toRows`, `ramps`, `meta`, `calibration`.

### Sequential or diverging — decided by the data

`chooseScale()` inspects the field rather than guessing:

- **Never crosses zero** → it is a *magnitude*, so a **sequential** ramp over
  `[0, max]`. Warming-since-today is positive everywhere under most scenarios;
  putting it on a diverging scale spends half the range on values that never
  occur and visibly flattens the spatial pattern.
- **Does cross zero** → it is a *polarity*, so a **symmetric diverging** scale,
  keeping the neutral midpoint meaning "no change". Needed for years before the
  baseline, and for genuine overshoot fields.

Both ramps are lightness-monotone per arm (arm asymmetry 1.1e-3 in OKLab), so
the encoding is invertible — a reader really can recover a value from the
legend. `validate_map.mjs` checks that round-trip: max error 0.016 K.

Worth knowing: SSP1-1.9 peaks and declines but stays **above** the 1995–2014
level through 2100, so it does *not* produce a negative field. Don't assume
the mitigation scenarios exercise the diverging path.

## WorldWide Telescope

```bash
pip install toasty --no-deps      # its pims dep is only for video loaders and won't build
pip install wwt_data_formats pillow pyyaml numpy scipy matplotlib

python3 export_wwt.py --scenario ssp245 --years 2030:2100:10 --depth 5
python3 validate_wwt.py --outdir wwt
```

Then open **`wwt/index_rel.wtml`** in WorldWide Telescope. It is a folder of
one Earth image set per year, so you can step through them.

WWT displays full-sphere imagery as a **TOAST** tile pyramid. Rather than guess
at a partial-coverage projection, this embeds the CONUS field in a full-globe
plate carrée canvas that is transparent everywhere else and lets `toasty`
resample it to TOAST. The geometry is then exactly right, and the layer only
paints over CONUS so WWT's own basemap shows through elsewhere. The WTML sets
`DataSetType="Earth"`, `ReferenceFrame="Earth"`, `Projection="Toast"`.

Also written, for other viewers:

| Path | For |
|---|---|
| `platecarree/*.png` | Global 2:1 plate carrée, transparent outside CONUS — Cesium, three.js, Blender, any globe. |
| `platecarree/*.kml` | Google Earth `GroundOverlay`. |
| `conus_crop/*.png` + `.pgw` | Tight CONUS crop with an ESRI world file — QGIS, ArcGIS. |
| `legend.png`, `manifest.json` | The colour bar, and the scale + per-year global ΔT + provenance. |

### Options that matter

`--scale-mode shared` (default) uses one colour scale for every frame, so the
years are comparable and the animation means something. The cost is real:
within-year spatial structure looks flat, because it *is* small next to the
total warming — at 2100 under SSP2-4.5 the CONUS spread is ~1.1 K against 2.9 K
of warming. `--scale-mode per-frame` shows the spatial pattern instead, at the
cost of every year looking equally warm. Neither is correct in general; pick by
the question you are asking. The manifest records which you used.

`--loop-only` maps the methane feedback's **own** contribution (with minus
without) rather than total warming. It is small — about +0.11 K CONUS mean by
2100 at γ = 20 — so it gets its own scale automatically; on the total-warming
scale it would be invisible.

`--depth` is the TOAST depth (default 5, about 0.04°/px — ample for 0.5° source
data). Tile subtrees that cannot touch CONUS are pruned, which is the
difference between 12 seconds and several minutes per frame: unfiltered,
toasty samples all 4^depth leaf tiles to discover that ~99% of them are empty.

## Replacing the synthetic pattern with real CMIP6

```bash
python3 test_ingest.py            # 12 checks: does the regression recover a known pattern?
python3 derive_pattern_from_cmip6.py --files 'cmip6/tas_*.nc' --model ACCESS-CM2
python3 export_bundle.py --pattern real_pattern.npz
```

The script does the standard thing (Santer et al. 1990; Tebaldi & Arblaster
2014; Wells et al. 2023): annual means, area-weighted global mean, anomalies
against 1850–1900, then per-grid-cell OLS of local on global. Regression is
through the origin by default, since a zero global anomaly must give a zero
local anomaly by construction; `--with-intercept` fits one anyway as a
linearity diagnostic. Repeat `--files`/`--model` for a multi-model mean — it
averages the *patterns*, never the raw fields, and reports the inter-model
spread.

Getting the data: ESGF (`variable=tas, frequency=mon,
experiment_id=historical,ssp245`) or the Pangeo cloud catalogue with
`intake-esm`, no downloads. Use **several models**: inter-model spread in `P`
exceeds inter-scenario spread, so one model's pattern is not "the" pattern.
The script's docstring has both recipes.

## What was verified

`node validate_map.mjs` → **49/49**. `python3 validate_wwt.py` → **80/80**.
`python3 test_ingest.py` → **12/12**.

Highlights, and the bugs they caught:

- **Pattern scaling is exact**: linear in the global anomaly to 0 relative
  error; rebasing matches `P × (G(t) − G(base))` to 1e-7 K.
- **Sampling**: exact at grid nodes; the bilinear midpoint equals the 4-cell
  mean; NaN offshore. Denver > San Francisco, Fargo > Miami.
- **TOAST geometry**: all 962,359 painted pixels fall inside the CONUS bounding
  box and 99.6% on CONUS land; Beijing, the mid-Atlantic, Winnipeg, Mexico City
  and the flipped-longitude mirror point are all empty. File counts prove
  nothing here — a longitude sign error would place the field over central Asia
  with every file still present.
- **Pixels decode back to the model**: reading colour out of the pyramid and
  inverting through the LUT recovers Fargo +2.86 K, Houston +2.20 K, Kansas
  City +2.66 K, San Francisco +1.95 K — within 0.025 K of the model field.
- **The ingest script recovers a known pattern** to max error 0.026 with 0.3 K
  of imposed noise, near-exactly without. It caught two real problems on first
  run: `chunks=` silently requires dask, and `use_cftime=` is deprecated in
  current xarray.
- Two bugs the harnesses caught that would otherwise have shipped: a `for name,
  la, lo in cities` loop leaking and clobbering the colour scale's `lo` with a
  longitude, and a hue-based "warmth" test metric that was wrong because the
  warm arm *darkens* as it warms.

## Limitations

- **Pattern scaling is a linear approximation.** Self-emulation errors are
  typically under 0.3 K, but out-of-sample errors exceed 0.5 K in the Northern
  Hemisphere mid-latitudes — which includes CONUS. It degrades most for
  strong-mitigation and overshoot pathways (20–50% time-series error, because
  regions peak at different times than the global mean) and where aerosol
  forcing patterns change (Wells et al. 2023, ESD 14, 817).
- **No internal variability.** These are forced-response fields, not weather.
  Any single year in reality would differ by several tenths of a kelvin.
- **Annual mean only.** Northern-US winter warming and Southwest summer warming
  are both amplified relative to the annual mean; a seasonal pattern would need
  DJF/JJA regressions.
- **Two known structural residuals in the synthetic pattern**: the interior
  Southwest fits ~0.06 low and the interior Deep South ~0.06 high. Both are
  aridity — dry soil cannot evaporatively cool, so arid regions warm more — and
  there is deliberately no aridity term, because that would mean inventing a
  second layer of structure on top of an already synthetic field.
- **The distance fields use a cos(mean latitude) approximation** for longitude
  spacing across a 75° span. Fine for a synthetic field; irrelevant once you
  swap in real CMIP6 data.
- **`--depth` above 9** changes toasty's filtered-tiling behaviour; not tested
  here.

## References

- Santer, B. D. et al. (1990). *Developing climate scenarios from equilibrium GCM results.* MPI Report 47.
- Mitchell, T. D. (2003). *Pattern scaling: an examination of the accuracy of the technique.* Climatic Change 60, 217–242.
- Tebaldi, C. & Arblaster, J. M. (2014). *Pattern scaling: its strengths and limitations.* Climatic Change 122, 459–471.
- Wells, C. D. et al. (2023). *Understanding pattern scaling errors across a range of emissions pathways.* Earth Syst. Dynam. 14, 817–834.
- IPCC AR6 WGII Ch.14 (North America): "continental intensification of warming", southwestern amplification.
- Natural Earth 1:50m cultural and physical vectors, via the `nvkelso/natural-earth-vector` mirror.
- AAS WorldWide Telescope: `toasty` and `wwt_data_formats`.
