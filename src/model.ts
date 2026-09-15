/**
 * The methane-temperature feedback model.
 *
 * Every number the science depends on is a named constant in PARAMS below, so
 * the whole model can be re-pointed by editing one object. Each carries its
 * source. Constants still carrying a guessed value are marked PLACEHOLDER.
 *
 * The one thing to know before trusting this: GCReW/SMARTX has never published
 * a temperature-response equation for its methane flux. Noyce & Megonigal
 * (2021) report only a correlation (R^2 = 0.41), and Noyce et al. (2023)
 * publish the *form* of their log-linear scaling model but not its fitted
 * coefficients. So the temperature sensitivity here is borrowed from a
 * cross-site synthesis, and only the baseline flux is a GCReW measurement.
 * See the README for what that costs us.
 *
 * The chain the model walks, once per simulated year:
 *
 *   marsh temperature  --(Q10 response, GCReW)-->  CH4 flux per m^2
 *   flux               --(wetland area scaling)-->  global CH4 emission
 *   emission           --(one-box lifetime)     -->  atmospheric CH4
 *   atmospheric CH4    --(radiative forcing)    -->  extra forcing
 *   forcing            --(climate sensitivity)  -->  global warming
 *   warming            --(feeds back)           -->  marsh temperature
 */

export interface ModelParams {
  /** Marsh soil temperature the baseline flux was measured at, deg C. */
  baselineMarshTempC: number;
  /** CH4 flux at baselineMarshTempC, mg CH4 per m^2 per hour. */
  baselineFluxMgPerM2PerHr: number;
  /** Factor the flux multiplies by per 10 deg C of warming. */
  q10: number;
  /** Global wetland CH4 emission in the baseline state, Tg CH4 per year. */
  baselineWetlandEmissionTgPerYr: number;
  /** Atmospheric CH4 in the baseline state, parts per billion. */
  baselineCh4Ppb: number;
  /** CH4 atmospheric lifetime, years. */
  ch4LifetimeYr: number;
  /** Tg of atmospheric CH4 per ppb of mixing ratio. */
  tgPerPpb: number;
  /** Atmospheric N2O, ppb. Held fixed; it enters the CH4 forcing as an overlap. */
  n2oPpb: number;
  /** Equilibrium warming per unit forcing, deg C per W/m^2. */
  climateSensitivity: number;
  /** How fast the surface approaches its equilibrium temperature, per year. */
  warmingResponseRate: number;
  /**
   * How much of global warming the marsh actually feels. 1 means the marsh
   * warms exactly as fast as the global mean.
   */
  marshAmplification: number;
  /**
   * Multiplies the strength of the returning half of the loop only.
   *
   * At 1 the model is honest and the feedback is very small: starting 2 deg C
   * warm adds about 0.05 deg C over 75 years, which is invisible on a chart.
   * Raise this to make the loop legible in a demo, and say on screen that it
   * has been raised. It does not change the flux the thermometer or the
   * canister show, only how much warming the extra methane is credited with.
   */
  feedbackExaggeration: number;
}

export const PARAMS: ModelParams = {
  // --- GCReW / SMARTX warming experiment ------------------------------------

  /* Ambient-plot growing-season daily mean soil temperature ran 20.7-22.4 degC
     over 2016-2019 (Noyce & Megonigal 2021), so 21.5 is the midpoint. No
     soil-temperature time series is archived with the public flux data, which
     is why this is a reported range rather than a fitted value.
     It cancels out of the Q10 response, which depends only on the difference
     from it, so it sets where the thermometer's dashed line sits and nothing
     else. It does fix the temperature at which the Q10 below is evaluated. */
  baselineMarshTempC: 21.5,

  /* Measured: C3 (Schoenoplectus americanus) ambient plots, growing season,
     20 +/- 5 umol CH4 m^-2 h^-1 = 0.32 mg m^-2 h^-1.
     Mueller et al. 2020, Nat. Commun. 11:5154, doi:10.1038/s41467-020-18763-4.
     The C4 (Spartina patens) community runs ~3x higher, at 1.04.

     This is deliberately the published 2019 figure, not the 0.280 that
     GCREW_TREATMENTS carries for the same plots. That one is mine, averaged
     over 2017-2024 from the archived data; the two differ because they cover
     different years, and interannual variation at this site is larger than the
     warming effect. Swap in 0.280 if you would rather the model baseline and
     the plotted ambient point be the same number. */
  baselineFluxMgPerM2PerHr: 0.32,

  /* BORROWED, not GCReW. Yvon-Durocher et al. 2014, Nature 507:488-491,
     doi:10.1038/nature13164: activation energy 0.96 eV, from 1553 paired
     flux-temperature observations across 126 sites.

     A Q10 is not constant under an Arrhenius law, so this is 0.96 eV evaluated
     at baselineMarshTempC above:
       Q10 = exp(E * 10 / (k * T * (T + 10))),  k = 8.617e-5 eV/K, T in kelvin
     which at 21.5 degC gives 3.459. The same conversion reproduces the paper's
     own "57-fold increase from 0 to 30 degC" (it gives 56.6), which is the
     check that the formula is right. Change baselineMarshTempC and this should
     be recomputed: 3.83 at 10 degC, 3.50 at 20, 3.36 at 25.
     The published CI of 0.88-1.08 eV spans Q10 3.12 to 4.04 here.

     Two honest alternatives, both defensible and both different:
       - 11.9: apparent Q10 fitted to SMARTX's own warming gradient, C3
         community. GCReW's actual response, but it bundles sulfate depletion
         and plant-trait shifts, so it is not a thermal Q10.
       - 3.45: the same fit for the C4 community, which happens to land close
         to the Arrhenius value above.
     The C3 response is threshold-like and the C4 response graded, so no single
     Q10 reproduces both communities. */
  q10: 3.459,

  // --- scaling one marsh up to the globe -----------------------------------

  /* Vegetated wetlands only, bottom-up, 2010-2019: 159 [119-203] Tg CH4/yr.
     Saunois et al. 2025 Global Methane Budget, ESSD 17:1873-1958,
     doi:10.5194/essd-17-1873-2025.

     Read this deliberately: the marsh is the *mechanism* on screen, not the
     quantitative driver. Global salt marsh emits only 0.26 Tg CH4/yr
     (Rosentreter et al. 2023) against these 159, about 0.16%, and the budget
     excludes salt marsh from "wetlands" on salinity anyway. A salt-marsh-only
     feedback would be climatically negligible and would not survive review.
     So the model applies the marsh's temperature response to the whole wetland
     pool, which is the defensible route and is validated: it yields 19.9
     Tg CH4/yr per degC, against the observationally constrained 24 +/- 10 of
     Zhang et al. 2026, doi:10.1038/s41561-026-01987-2. */
  baselineWetlandEmissionTgPerYr: 159,

  // --- atmospheric box -----------------------------------------------------

  baselineCh4Ppb: 1866.3, // 2019, IPCC AR6 WG1 Table 7.5
  /* Perturbation lifetime, 11.8 +/- 1.8 yr (AR6 Table 7.15). This is the right
     decay constant for an emissions-driven box; the 9.1 yr figure is the total
     atmospheric lifetime and would under-accumulate. */
  ch4LifetimeYr: 11.8,
  tgPerPpb: 2.75, // Prather, Holmes & Hsu 2012, doi:10.1029/2012GL051440
  n2oPpb: 332.1, // 2019, AR6 Table 7.5

  // --- forcing and temperature --------------------------------------------

  /* ECS 3.0 deg C / 3.93 W m^-2 per CO2 doubling = 0.76, both AR6-assessed.
     AR6 does not assess this ratio itself. Using TCR instead would give 0.46. */
  climateSensitivity: 0.76,
  warmingResponseRate: 0.3, // PLACEHOLDER: how fast the surface catches up
  marshAmplification: 1.0,
  feedbackExaggeration: 1.0,
};

/**
 * What SMARTX actually measured, for plotting against the smooth curve.
 *
 * Growing season (May-Sep), ambient-CO2 plots, 2017-2024. Computed from the
 * archived chamber fluxes (2424 observations, 30 plots, CC BY 4.0,
 * doi:10.25573/serc.31581154) as the mean of the three replicate plot means,
 * with the standard error across those three plots.
 *
 * Note the shape, which is the most interesting thing in the experiment and
 * the thing a single Q10 destroys: the C3 (Schoenoplectus) response is
 * threshold-like, near-flat to +3.4 degC and then 4.6x ambient at +5.1, because
 * the plant transports oxygen into the soil until methane production
 * overwhelms it. The C4 (Spartina) response is shallower and non-monotonic.
 */
export interface TreatmentPoint {
  /** Warming above ambient, deg C. */
  warmingC: number;
  /** Plant community. */
  community: "C3" | "C4";
  /** Mean flux, micromol CH4 per m^2 per day. */
  fluxUmolPerM2PerDay: number;
  /** Standard error across the three replicate plots, same units. */
  standardError: number;
  /** Mean flux converted to the units the model works in. */
  fluxMgPerM2PerHr: number;
  /** Flux as a multiple of that community's ambient plots. */
  ratioToAmbient: number;
}

export const GCREW_TREATMENTS: TreatmentPoint[] = [
  { warmingC: 0, community: "C3", fluxUmolPerM2PerDay: 419, standardError: 71, fluxMgPerM2PerHr: 0.280, ratioToAmbient: 1.00 },
  { warmingC: 1.7, community: "C3", fluxUmolPerM2PerDay: 487, standardError: 74, fluxMgPerM2PerHr: 0.325, ratioToAmbient: 1.16 },
  { warmingC: 3.4, community: "C3", fluxUmolPerM2PerDay: 766, standardError: 143, fluxMgPerM2PerHr: 0.512, ratioToAmbient: 1.83 },
  { warmingC: 5.1, community: "C3", fluxUmolPerM2PerDay: 1950, standardError: 641, fluxMgPerM2PerHr: 1.303, ratioToAmbient: 4.65 },
  { warmingC: 0, community: "C4", fluxUmolPerM2PerDay: 716, standardError: 175, fluxMgPerM2PerHr: 0.478, ratioToAmbient: 1.00 },
  { warmingC: 1.7, community: "C4", fluxUmolPerM2PerDay: 1011, standardError: 216, fluxMgPerM2PerHr: 0.676, ratioToAmbient: 1.41 },
  { warmingC: 3.4, community: "C4", fluxUmolPerM2PerDay: 976, standardError: 123, fluxMgPerM2PerHr: 0.652, ratioToAmbient: 1.36 },
  { warmingC: 5.1, community: "C4", fluxUmolPerM2PerDay: 1281, standardError: 249, fluxMgPerM2PerHr: 0.856, ratioToAmbient: 1.79 },
];

/** One simulated year of the feedback loop. */
export interface YearState {
  year: number;
  /** Global mean warming above the baseline state, deg C. */
  globalAnomalyC: number;
  /** Marsh soil temperature, deg C. */
  marshTempC: number;
  /** CH4 flux out of the marsh, mg CH4 per m^2 per hour. */
  fluxMgPerM2PerHr: number;
  /** Flux as a multiple of the baseline flux. */
  fluxRatio: number;
  /** CH4 molecules leaving one square metre of marsh each second. */
  moleculesPerM2PerSec: number;
  /** Global wetland CH4 emission, Tg CH4 per year. */
  wetlandEmissionTgPerYr: number;
  /** Atmospheric CH4 mixing ratio, ppb. */
  ch4Ppb: number;
  /** CH4 radiative forcing above the baseline state, W/m^2. */
  forcingWPerM2: number;
}

const AVOGADRO = 6.02214076e23;
const CH4_MOLAR_MASS_G = 16.043;

/** mg CH4 per m^2 per hour -> molecules per m^2 per second. */
export function fluxToMolecules(fluxMgPerM2PerHr: number): number {
  const gramsPerSec = (fluxMgPerM2PerHr / 1000) / 3600;
  return (gramsPerSec / CH4_MOLAR_MASS_G) * AVOGADRO;
}

/** The GCReW temperature response, evaluated at an arbitrary temperature. */
export function marshFlux(marshTempC: number, p: ModelParams = PARAMS): number {
  return p.baselineFluxMgPerM2PerHr * Math.pow(p.q10, (marshTempC - p.baselineMarshTempC) / 10);
}

/* IPCC AR6 WG1 Table 7.SM.1, the Meinshausen et al. 2020 fit to Etminan et
   al. 2016. The bracket is linear in sqrt(M) and sqrt(N), and the b3 term is
   the N2O band overlap. Checked against the published value: M = 1866.3,
   N = 332.1 gives SARF 0.6325 and ERF 0.544 W/m^2, matching AR6 Table 7.5. */
const AR6_A3 = -8.9603e-5;
const AR6_B3 = -1.2462e-4;
const AR6_D3 = 0.045194;
/** Pre-industrial CH4, ppb. AR6 WG1 Chapter 2. */
const CH4_1750_PPB = 729.2;
/** Tropospheric adjustment turning stratospherically-adjusted RF into ERF. */
const AR6_ERF_ADJUSTMENT = 0.86;

/** CH4 effective radiative forcing relative to 1750, W/m^2. */
function ch4ErfSince1750(ch4Ppb: number, p: ModelParams): number {
  const sarf =
    (AR6_A3 * Math.sqrt(ch4Ppb) + AR6_B3 * Math.sqrt(p.n2oPpb) + AR6_D3)
    * (Math.sqrt(ch4Ppb) - Math.sqrt(CH4_1750_PPB));
  return AR6_ERF_ADJUSTMENT * sarf;
}

/** The extra CH4 forcing this run has produced, above the baseline state. */
function ch4Forcing(ch4Ppb: number, p: ModelParams): number {
  return ch4ErfSince1750(ch4Ppb, p) - ch4ErfSince1750(p.baselineCh4Ppb, p);
}

/**
 * Every CH4 source other than wetlands, inferred rather than specified: it is
 * whatever holds the baseline concentration steady, so a starting anomaly of
 * zero gives a flat line instead of a slow drift.
 */
function nonWetlandEmission(p: ModelParams): number {
  return (p.baselineCh4Ppb / p.ch4LifetimeYr) * p.tgPerPpb - p.baselineWetlandEmissionTgPerYr;
}

function describe(year: number, globalAnomalyC: number, ch4Ppb: number, p: ModelParams): YearState {
  const marshTempC = p.baselineMarshTempC + p.marshAmplification * globalAnomalyC;
  const fluxMgPerM2PerHr = marshFlux(marshTempC, p);
  const fluxRatio = fluxMgPerM2PerHr / p.baselineFluxMgPerM2PerHr;

  return {
    year,
    globalAnomalyC,
    marshTempC,
    fluxMgPerM2PerHr,
    fluxRatio,
    moleculesPerM2PerSec: fluxToMolecules(fluxMgPerM2PerHr),
    wetlandEmissionTgPerYr: p.baselineWetlandEmissionTgPerYr * fluxRatio,
    ch4Ppb,
    forcingWPerM2: ch4Forcing(ch4Ppb, p),
  };
}

export interface RunOptions {
  /** Year the simulation starts at. */
  startYear?: number;
  /** How many years to step. */
  years?: number;
  params?: ModelParams;
}

/**
 * Run the loop from a starting global temperature anomaly.
 *
 * The user's "starting temperature" is an anomaly above the baseline state, so
 * 0 reproduces the baseline and the curve stays flat apart from the feedback.
 */
export function runModel(startingAnomalyC: number, options: RunOptions = {}): YearState[] {
  const { startYear = 2026, years = 75, params: p = PARAMS } = options;

  let anomaly = startingAnomalyC;
  let ch4 = p.baselineCh4Ppb;
  const other = nonWetlandEmission(p);

  const states: YearState[] = [describe(startYear, anomaly, ch4, p)];

  for (let i = 1; i <= years; i++) {
    const previous = states[i - 1];

    // atmospheric box: emission in, decay out
    const emission = previous.wetlandEmissionTgPerYr + other;
    ch4 += emission / p.tgPerPpb - ch4 / p.ch4LifetimeYr;

    // surface temperature relaxes toward the warming the new forcing implies,
    // on top of whatever anomaly the user started with
    const equilibrium = startingAnomalyC
      + p.feedbackExaggeration * p.climateSensitivity * ch4Forcing(ch4, p);
    anomaly += p.warmingResponseRate * (equilibrium - anomaly);

    states.push(describe(startYear + i, anomaly, ch4, p));
  }

  return states;
}

/**
 * The baseline run, used as the "no extra warming" comparison line. Computed
 * once because it never changes.
 */
export const BASELINE_RUN = runModel(0);
