/**
 * ch4map.js - turn a global temperature anomaly into a CONUS map, by pattern
 * scaling. Companion to ch4feedback.js; dependency-free ES module.
 *
 *   dT(x, y, t)  =  P(x, y) * [ dT_global(t) - dT_global(baseline) ]
 *
 * P is a dimensionless field - local kelvin per global kelvin. Because the
 * baseline subtraction commutes with the multiply, rebasing to "warming since
 * today" is exact rather than an approximation.
 *
 * A field is one multiply per grid cell (~3300 cells), so a year-slider can
 * regenerate the whole map every frame.
 *
 * *** THE BUNDLED PATTERN IS SYNTHETIC. *** It is not derived from CMIP6
 * output. Check `bundle.meta.synthetic` and surface it in your UI; run
 * derive_pattern_from_cmip6.py to replace it with a real one. The schema is
 * identical, so nothing here changes.
 *
 * Pattern scaling is also a linear approximation with known failure modes -
 * see `bundle.meta.limits`. It carries no internal variability: these are
 * forced-response fields, not weather.
 *
 * Usage
 *   import { run } from './ch4feedback.js';
 *   import { createMapper } from './ch4map.js';
 *
 *   const [fb, pat] = await Promise.all([
 *     fetch('./ssp-ch4-feedback.json').then(r => r.json()),
 *     fetch('./conus-pattern.json').then(r => r.json()),
 *   ]);
 *   const map = createMapper(pat);
 *   const result = run(fb, 'ssp245', { gammaWetland: 20, startYear: 1850, endYear: 2100 });
 *   const field = map.field(result, 2075);        // vs 1995-2014 by default
 *   field.values;                                  // Float32Array, NaN off-land
 */

/** Default "today" baseline: the CMIP6 present-day reference period. */
export const DEFAULT_BASELINE = [1995, 2014];

/**
 * @param {object} bundle parsed conus-pattern.json
 */
export function createMapper(bundle) {
  const { nlon, nlat, step } = bundle.meta.grid;
  const nodata = bundle.meta.nodata;
  const lat = Float64Array.from(bundle.lat);
  const lon = Float64Array.from(bundle.lon);

  // pattern with nodata turned into NaN, so arithmetic propagates it
  const P = new Float32Array(nlon * nlat);
  for (let i = 0; i < P.length; i++) {
    const v = bundle.pattern[i];
    P[i] = v === nodata ? NaN : v;
  }
  const stateIndex = bundle.state_index ? Int16Array.from(bundle.state_index) : null;

  // cos(latitude) area weights, for honest spatial means
  const weight = new Float64Array(nlon * nlat);
  for (let j = 0; j < nlat; j++) {
    const w = Math.cos((lat[j] * Math.PI) / 180);
    for (let i = 0; i < nlon; i++) weight[j * nlon + i] = w;
  }

  /** Mean global anomaly over [y0, y1] in a ch4feedback.js result. */
  function baselineMean(result, [y0, y1]) {
    let sum = 0, n = 0;
    for (let i = 0; i < result.year.length; i++) {
      if (result.year[i] >= y0 && result.year[i] <= y1) {
        sum += result.temperature[i]; n++;
      }
    }
    if (!n) {
      throw new Error(`baseline ${y0}-${y1} not inside the run ` +
        `(${result.year[0]}-${result.year[result.year.length - 1]})`);
    }
    return sum / n;
  }

  function indexOfYear(result, year) {
    for (let i = 0; i < result.year.length; i++) if (result.year[i] === year) return i;
    return -1;
  }

  /** Scale the pattern by a scalar global anomaly. The primitive. */
  function fieldFromDelta(globalDelta, extra = {}) {
    const values = new Float32Array(P.length);
    let min = Infinity, max = -Infinity, wsum = 0, vsum = 0;
    for (let i = 0; i < P.length; i++) {
      const v = P[i] * globalDelta;
      values[i] = v;
      if (Number.isFinite(v)) {
        if (v < min) min = v;
        if (v > max) max = v;
        vsum += v * weight[i]; wsum += weight[i];
      }
    }
    return {
      values, globalDelta,
      min: wsum ? min : NaN, max: wsum ? max : NaN,
      mean: wsum ? vsum / wsum : NaN,
      nlon, nlat, lat, lon, step,
      ...extra,
    };
  }

  /**
   * Map of warming in `year` relative to a baseline period.
   * @param {object} result  a ch4feedback.js run()
   * @param {number} year
   * @param {object} [opts]  { baseline: [y0, y1] }
   */
  function field(result, year, opts = {}) {
    const baseline = opts.baseline ?? DEFAULT_BASELINE;
    const i = indexOfYear(result, year);
    if (i < 0) throw new Error(`year ${year} not in the run`);
    const base = baselineMean(result, baseline);
    return fieldFromDelta(result.temperature[i] - base, { year, baseline });
  }

  /**
   * Map of the methane loop's OWN contribution in `year` - the with-minus-
   * without-feedback difference, spatialised. No baseline subtraction: the
   * difference is already a difference, and rebasing it would remove most of
   * what you are trying to show.
   * @param {object} decomposed  a ch4feedback.js runDecomposed()
   */
  function loopField(decomposed, year) {
    const i = indexOfYear(decomposed.withFeedback, year);
    if (i < 0) throw new Error(`year ${year} not in the run`);
    return fieldFromDelta(decomposed.deltaTemperature[i], { year, loop: true });
  }

  /** Every year at once, for pre-rendering an animation. */
  function fieldSeries(result, years, opts = {}) {
    return years.map((y) => field(result, y, opts));
  }

  /** Bilinear sample at a point, for tooltips. NaN outside the land mask. */
  function sample(f, latDeg, lonDeg) {
    const x = (lonDeg - lon[0]) / step;
    const y = (latDeg - lat[0]) / step;
    const i0 = Math.floor(x), j0 = Math.floor(y);
    if (i0 < 0 || j0 < 0 || i0 >= nlon - 1 || j0 >= nlat - 1) return NaN;
    const tx = x - i0, ty = y - j0;
    const v = (j, i) => f.values[j * nlon + i];
    const a = v(j0, i0), b = v(j0, i0 + 1), c = v(j0 + 1, i0), d = v(j0 + 1, i0 + 1);
    if (![a, b, c, d].every(Number.isFinite)) {
      // near the coast: fall back to the nearest valid cell
      const cands = [[j0, i0], [j0, i0 + 1], [j0 + 1, i0], [j0 + 1, i0 + 1]]
        .filter(([j, i]) => Number.isFinite(v(j, i)));
      if (!cands.length) return NaN;
      let bestD = Infinity, best = NaN;
      for (const [j, i] of cands) {
        const dd = (j - y) ** 2 + (i - x) ** 2;
        if (dd < bestD) { bestD = dd; best = v(j, i); }
      }
      return best;
    }
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
  }

  /** Area-weighted mean per state -> [{name, value}], for hover readouts. */
  function stateMeans(f) {
    if (!stateIndex) return [];
    const names = bundle.state_names ?? [];
    const sum = new Float64Array(names.length);
    const wt = new Float64Array(names.length);
    for (let i = 0; i < f.values.length; i++) {
      const k = stateIndex[i];
      if (k < 0 || !Number.isFinite(f.values[i])) continue;
      sum[k] += f.values[i] * weight[i];
      wt[k] += weight[i];
    }
    return names.map((name, k) => ({
      name, value: wt[k] ? sum[k] / wt[k] : NaN,
    }));
  }

  // ---------------------------------------------------------------- colour --

  const hexToRgb = (h) => [
    parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16),
  ];
  const DIVERGING = bundle.ramp.diverging.map(hexToRgb);
  const SEQUENTIAL = (bundle.ramp.sequential ?? bundle.ramp.diverging
    .slice(Math.floor(bundle.ramp.diverging.length / 2))).map(hexToRgb);

  /**
   * Pick the encoding from the data rather than by habit.
   *
   * A field that never crosses zero is a MAGNITUDE and takes a sequential
   * ramp over [0, max]. Putting it on a diverging scale spends half the range
   * on values that never occur and visibly flattens the spatial pattern -
   * which is exactly what happens to "warming since today" under most
   * scenarios, since it is positive everywhere.
   *
   * A field that does cross zero - an overshoot pathway like SSP1-1.9 after
   * its peak, or early years against a present-day baseline - is a POLARITY
   * and takes a SYMMETRIC diverging scale, so the neutral midpoint keeps
   * meaning "no change".
   *
   * Pass the same scale to every frame of an animation. Rescaling per frame is
   * the classic way to make one meaningless.
   *
   * @param {object|object[]} fields one field or all the frames
   * @returns {{kind: 'sequential'|'diverging', lo: number, hi: number}}
   */
  function chooseScale(fields) {
    const list = Array.isArray(fields) ? fields : [fields];
    let lo = Infinity, hi = -Infinity;
    for (const f of list) {
      if (Number.isFinite(f.min)) lo = Math.min(lo, f.min);
      if (Number.isFinite(f.max)) hi = Math.max(hi, f.max);
    }
    if (!Number.isFinite(lo)) return { kind: 'sequential', lo: 0, hi: 1 };
    const span = Math.max(Math.abs(lo), Math.abs(hi));
    const tidy = (v) => Math.ceil(v * 20) / 20;
    if (lo < -0.05 * span) {
      const h = tidy(span);
      return { kind: 'diverging', lo: -h, hi: h };
    }
    return { kind: 'sequential', lo: 0, hi: tidy(hi) };
  }

  /** Colour for a value on a scale from chooseScale(). -> [r,g,b] or null. */
  function colorFor(v, scale) {
    if (!Number.isFinite(v)) return null;
    const stops = scale.kind === 'diverging' ? DIVERGING : SEQUENTIAL;
    const t = Math.max(0, Math.min(1, (v - scale.lo) / (scale.hi - scale.lo)));
    const x = t * (stops.length - 1);
    const i = Math.max(0, Math.min(stops.length - 2, Math.floor(x)));
    const fr = x - i;
    const a = stops[i], b = stops[i + 1];
    return [
      Math.round(a[0] + (b[0] - a[0]) * fr),
      Math.round(a[1] + (b[1] - a[1]) * fr),
      Math.round(a[2] + (b[2] - a[2]) * fr),
    ];
  }

  /** Evenly spaced legend entries for a scale. */
  function legendStops(scale, n = 5) {
    const out = [];
    for (let k = 0; k < n; k++) {
      const v = scale.lo + (scale.hi - scale.lo) * (k / (n - 1));
      out.push({ value: v, rgb: colorFor(v, scale) });
    }
    return out;
  }

  /**
   * Render a field to ImageData at grid resolution (nlon x nlat), row 0 at the
   * TOP (north), ready for putImageData then drawImage to scale it up.
   * Off-land cells are fully transparent.
   */
  function toImageData(f, opts = {}) {
    const scale = opts.scale ?? chooseScale(f);
    const data = new Uint8ClampedArray(nlon * nlat * 4);
    for (let j = 0; j < nlat; j++) {
      const jSrc = nlat - 1 - j;              // flip: lat ascends, canvas descends
      for (let i = 0; i < nlon; i++) {
        const v = f.values[jSrc * nlon + i];
        const o = (j * nlon + i) * 4;
        const c = colorFor(v, scale);
        if (!c) { data[o + 3] = 0; continue; }
        data[o] = c[0]; data[o + 1] = c[1]; data[o + 2] = c[2]; data[o + 3] = 255;
      }
    }
    return { imageData: new ImageData(data, nlon, nlat), scale };
  }

  // ------------------------------------------------------------ projection --

  /**
   * Plate carree with a cos(latitude) aspect correction, so the map is not
   * stretched. Returns { project, unproject, width, height }.
   */
  function makeProjection({ width, height, padding = 0 } = {}) {
    const lon0 = lon[0], lon1 = lon[nlon - 1] + step;
    const lat0 = lat[0], lat1 = lat[nlat - 1] + step;
    const k = Math.cos(((lat0 + lat1) / 2 * Math.PI) / 180);
    const wDeg = (lon1 - lon0) * k, hDeg = lat1 - lat0;
    const availW = (width ?? 900) - 2 * padding;
    const availH = (height ?? Math.round((width ?? 900) * hDeg / wDeg)) - 2 * padding;
    const s = Math.min(availW / wDeg, availH / hDeg);
    const offX = padding + (availW - wDeg * s) / 2;
    const offY = padding + (availH - hDeg * s) / 2;
    return {
      project: (lonDeg, latDeg) => [
        offX + (lonDeg - lon0) * k * s,
        offY + (lat1 - latDeg) * s,
      ],
      unproject: (px, py) => [
        lon0 + (px - offX) / (k * s),
        lat1 - (py - offY) / s,
      ],
      bbox: [lon0, lat0, lon1, lat1],
      scale: s,
      width: availW + 2 * padding,
      height: availH + 2 * padding,
    };
  }

  /** Stroke the state outlines onto a 2D context using a projection. */
  function drawOutlines(ctx, projection, opts = {}) {
    ctx.save();
    ctx.strokeStyle = opts.stroke ?? 'rgba(11,11,11,0.28)';
    ctx.lineWidth = opts.lineWidth ?? 1;
    ctx.lineJoin = 'round';
    for (const st of bundle.outlines) {
      for (const ring of st.rings) {
        ctx.beginPath();
        for (let k = 0; k < ring.length; k++) {
          const [px, py] = projection.project(ring[k][0], ring[k][1]);
          if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  return {
    // fields
    field, loopField, fieldFromDelta, fieldSeries,
    // queries
    sample, stateMeans, baselineMean,
    // colour
    colorFor, chooseScale, legendStops, toImageData,
    ramps: { diverging: bundle.ramp.diverging, sequential: bundle.ramp.sequential },
    // geometry
    makeProjection, drawOutlines, outlines: bundle.outlines,
    // grid + provenance
    grid: { nlon, nlat, step, lat, lon }, pattern: P, weight,
    meta: bundle.meta, calibration: bundle.calibration,
    isSynthetic: !!bundle.meta.synthetic,
  };
}
