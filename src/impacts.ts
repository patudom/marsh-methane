/**
 * Human impacts of a given amount of global warming.
 *
 * Two things to understand before touching this file.
 *
 * **Baselines.** Every IPCC warming level is defined against 1850-1900, but the
 * model in model.ts works in anomalies above its 2019 state. Those are not the
 * same scale and mixing them is a whole degree of error. AR6 WG1 SPM: global
 * surface temperature in 2011-2020 was 1.09 [0.95 to 1.20] degC above
 * 1850-1900. So anchors here are stored at their *published* AR6 level and
 * converted on the way in. A model anomaly of +2 is an AR6 level of 3.09.
 *
 * **Shape.** Anchors are values at discrete warming levels, not per-degree
 * slopes, because most of these are non-linear and two of them are thresholds.
 * Coral loss saturates above 2 degC and carries no information after that;
 * hot-extreme frequency roughly triples between 2 and 4 degC. A single slope
 * through either would be actively misleading.
 *
 * Each entry says whether it is published at these levels or derived here.
 */

/**
 * Warming already realised at the model's baseline, in AR6 terms.
 * IPCC AR6 WG1 SPM A.1.2: 1.09 [0.95-1.20] degC, 2011-2020 vs 1850-1900.
 *
 * ⚠ KNOWN INCONSISTENCY, left for a scientist to settle. The model's anomalies
 * are now explicitly relative to **2026**, since the user picks warming by 2100
 * relative to today, but this constant is the 2011-2020 mean, effectively
 * centred on 2015. That is roughly a decade of unaccounted warming, on the order
 * of 0.2 degC at the assessed rate, which pushes every impact figure low by
 * something like 10-25% in the mid-range scenarios.
 *
 * It was not changed here because this is a science decision, not an interface
 * one, and because the coral anchor at line ~131 is deliberately pinned to this
 * same constant as its definition of "today" -- moving it also moves that
 * published curve. Change both together, deliberately.
 */
export const AR6_WARMING_IN_2019_C = 1.09;

export interface ImpactAnchor {
  /** Warming level above 1850-1900, i.e. as the source publishes it. */
  ar6WarmingC: number;
  value: number;
}

export interface Impact {
  id: string;
  /** Name for the dropdown. */
  label: string;
  /** Unit shown beside the number. */
  unit: string;
  /** Decimal places in the readout. */
  precision: number;
  /** What the number means, and against what baseline. */
  note: string;
  /** Short source credit shown under the readout. */
  source: string;
  /** Values at warming levels, interpolated between. */
  anchors: ImpactAnchor[];
  /** True when the anchors are published at these levels rather than derived. */
  published: boolean;
}

export const IMPACTS: Impact[] = [
  {
    id: "sea-level",
    label: "Sea level rise",
    unit: "cm by 2100",
    precision: 0,
    note: "Global mean sea level, median projection, relative to 1995–2014.",
    source: "AR6 WG1 Table 9.10",
    // Published medians. Above 3 degC AR6 states there is deep uncertainty and
    // that other ice-sheet approaches give substantially different answers; at
    // 5 degC expert judgement spans 0.7-1.6 m rather than 0.69-1.05.
    anchors: [
      { ar6WarmingC: 1.5, value: 44 },
      { ar6WarmingC: 2, value: 51 },
      { ar6WarmingC: 3, value: 61 },
      { ar6WarmingC: 4, value: 70 },
      { ar6WarmingC: 5, value: 81 },
    ],
    published: true,
  },
  {
    id: "hot-extremes",
    label: "Extreme heat frequency",
    unit: "× more often",
    precision: 1,
    note: "A heat extreme that used to come once in 50 years, now per 50 years.",
    source: "AR6 WG1 Figure SPM.6",
    // Published. Deliberately a hazard rather than an exposure: AR6 has no
    // statement of the form "X% of people exposed at Y degC", and the
    // niche-based population numbers are driven more by the population
    // projection and a no-migration assumption than by temperature.
    // AR6 publishes no 3 degC column, so that region is interpolation.
    anchors: [
      { ar6WarmingC: 1, value: 4.8 },
      { ar6WarmingC: 1.5, value: 8.6 },
      { ar6WarmingC: 2, value: 13.9 },
      { ar6WarmingC: 4, value: 39.2 },
    ],
    published: true,
  },
  {
    id: "maize-yield",
    label: "Maize yield",
    unit: "%",
    precision: 1,
    note: "Global maize yield, no CO₂ fertilisation, no adaptation.",
    source: "Zhao et al. 2017",
    /* Zhao et al. 2017 PNAS, doi:10.1073/pnas.1701762114: -7.4 +/- 4.5% per
       degC of global mean warming. Maize alone, not a staple average: at high
       warming maize and wheat move in opposite directions, so a blended figure
       conceals the result rather than summarising it. AR6 WG2 Ch5 endorses the
       paper's 3-7%/degC range.
       Linearity is the authors' own assumption, and they warn a +4 degC value
       is likely conservative because the real response is non-linear.
       Anchored at 1 degC, roughly the study's present-day reference. */
    anchors: [
      { ar6WarmingC: 1, value: 0 },
      { ar6WarmingC: 1.5, value: -3.7 },
      { ar6WarmingC: 2, value: -7.4 },
      { ar6WarmingC: 3, value: -14.8 },
      { ar6WarmingC: 4, value: -22.2 },
      { ar6WarmingC: 5, value: -29.6 },
    ],
    published: true,
  },
  {
    id: "coral",
    label: "Coral reefs lost",
    unit: "% further loss",
    precision: 0,
    note: "Warm-water reefs lost beyond today's already-degraded state.",
    source: "IPCC SR1.5 Ch3; AR6 WG2 Ch3",
    /* Published: 70-90% further loss at 1.5 degC (80 is the midpoint), and
       >99% at 2 degC or more. The zero at 1.09 is true by construction, since
       the metric is loss *compared to today* -- the ramp between it and 1.5
       degC is interpolation, not a published curve.
       This one saturates: past 2 degC the dial is flat because the published
       answer carries no further information. */
    anchors: [
      { ar6WarmingC: AR6_WARMING_IN_2019_C, value: 0 },
      { ar6WarmingC: 1.5, value: 80 },
      { ar6WarmingC: 2, value: 99 },
      { ar6WarmingC: 5, value: 100 },
    ],
    published: true,
  },
  {
    id: "species",
    label: "Species at extinction risk",
    unit: "% of species assessed",
    precision: 0,
    note: "Median estimate at very high risk. The upper bound rises far faster.",
    source: "AR6 WG2 Ch2 §2.5.1.3",
    /* Published medians. The matching maximum likely range is 14/18/29/39/48%,
       and it is the tail rather than the median that carries AR6's qualitative
       "increases steeply" -- the medians are close to linear at about
       1.7 points per degC. Pick one framing and say which; this is the median.
       Note AR6 Figure 2.7 is not independent of Urban 2015: 126 of its 178
       estimates are digitised from that paper. */
    anchors: [
      { ar6WarmingC: 1.5, value: 9 },
      { ar6WarmingC: 2, value: 10 },
      { ar6WarmingC: 3, value: 12 },
      { ar6WarmingC: 4, value: 13 },
      { ar6WarmingC: 5, value: 15 },
    ],
    published: true,
  },
  {
    id: "coastal-flooding",
    label: "Coastal flood exposure",
    unit: "× today's exposed population",
    precision: 2,
    note: "People in the 100-year floodplain, no population growth or new defences.",
    source: "Derived: AR6 WG2 SPM B.4.5 chained onto Table 9.10",
    /* DERIVED, and the only entry here that is. Two steps, both stated so the
       chain can be checked:
         1. AR6 Table 9.10 sea level at each warming level, shifted by -5.5 cm
            to move it from a 1995-2014 baseline onto the 2020 baseline that
            the exposure figures use. The shift is the assessed 3.7 mm/yr for
            2006-2018 applied across the gap.
         2. AR6 WG2 SPM B.4.5 / Haasnoot et al. 2021: exposure is 1.2x at
            0.15 m, 2x at 0.75 m and 3x at 1.4 m above 2020, interpolated.
       Baselines are the trap here. Haasnoot's own published present-day figure
       is 68 million in the 100-year floodplain, while Kulp & Strauss 2019 get
       about 250 million, and the gap is the elevation model and the
       coastal-defence assumption, not temperature. Across all published global
       estimates the spread is 88 million to 1.4 billion. This is a multiplier
       for that reason: do not pair it with an absolute count from another study.

       Also unsettled: Haasnoot's curve accelerates, so most exposure arrives
       late, and the interpolation below follows it. Vernimmen & Hooijer 2023,
       on lidar rather than radar elevation data, find the opposite curvature,
       with exposure rising fastest in the first metre. */
    anchors: [
      { ar6WarmingC: 1.5, value: 1.51 },
      { ar6WarmingC: 2, value: 1.61 },
      { ar6WarmingC: 3, value: 1.74 },
      { ar6WarmingC: 4, value: 1.86 },
      { ar6WarmingC: 5, value: 2.01 },
    ],
    published: false,
  },
];

/**
 * The impact at a model anomaly, linearly interpolated between the anchors and
 * held flat outside them.
 *
 * Held flat rather than extrapolated on purpose. Below the lowest anchor the
 * published studies do not speak, and several of these impacts are committed or
 * hysteretic -- sea level rise, coral loss and extinction do not run backwards
 * if the world cools. Running a straight line outwards would invent numbers in
 * exactly the regime where the relationships stop being linear.
 */
export function impactAt(impact: Impact, anomalyC: number): number {
  const level = ar6LevelFor(anomalyC);
  const anchors = impact.anchors;

  if (level <= anchors[0].ar6WarmingC) { return anchors[0].value; }

  const last = anchors[anchors.length - 1];
  if (level >= last.ar6WarmingC) { return last.value; }

  for (let i = 1; i < anchors.length; i++) {
    const low = anchors[i - 1];
    const high = anchors[i];
    if (level <= high.ar6WarmingC) {
      const span = high.ar6WarmingC - low.ar6WarmingC;
      const fraction = span === 0 ? 0 : (level - low.ar6WarmingC) / span;
      return low.value + fraction * (high.value - low.value);
    }
  }
  return last.value;
}

/** A model anomaly above 2019, expressed as an AR6 level above 1850-1900. */
export function ar6LevelFor(anomalyC: number): number {
  return anomalyC + AR6_WARMING_IN_2019_C;
}

/** True when the level sits outside the anchors, so the readout can say so. */
export function isExtrapolated(impact: Impact, anomalyC: number): boolean {
  const level = ar6LevelFor(anomalyC);
  const anchors = impact.anchors;
  return level < anchors[0].ar6WarmingC || level > anchors[anchors.length - 1].ar6WarmingC;
}
