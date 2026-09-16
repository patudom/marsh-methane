# Marsh Methane

An interactive prototype showing how a warming salt marsh emits more methane,
and how that methane warms the climate further. The science is anchored on the
Global Change Research Wetland (GCReW) at the Smithsonian Environmental Research
Center in Edgewater, Maryland, and specifically on its SMARTX whole-ecosystem
warming experiment.

This document records every number in the interface, where it came from, and
what we assumed to get from one end of the chain to the other. It is meant to be
read by someone checking the science, not only by someone running the code.

Built on the structure of the CosmicDS `why-roman` mini-project: Vue 3, Vuetify
3, and WorldWide Telescope through `@wwtelescope/engine-pinia`, bundled with
Vite and packaged with Yarn 4.

```
yarn install
yarn dev          # http://localhost:5173
yarn build        # runs type-check and build together; fails if either fails
yarn lint
```

## Contents

1. [What the interface does](#1-what-the-interface-does)
2. [The reasoning chain, step by step](#2-the-reasoning-chain-step-by-step)
3. [Every constant and its source](#3-every-constant-and-its-source)
4. [The measured GCReW data](#4-the-measured-gcrew-data)
5. [Where the model and the measurements disagree](#5-where-the-model-and-the-measurements-disagree)
6. [The human impacts panel](#6-the-human-impacts-panel)
7. [What we checked, and what it proved](#7-what-we-checked-and-what-it-proved)
8. [Honest weaknesses](#8-honest-weaknesses)
9. [Two transcription traps we avoided](#9-two-transcription-traps-we-avoided)
10. [References](#10-references)
11. [Code map and known gaps](#11-code-map-and-known-gaps)

---

## 1. What the interface does

The screen is three blocks, side by side in landscape and stacked in portrait.

**Block one** holds every control and every readout. The user chooses a starting
global temperature anomaly, from −2.0 to +4.0 °C, and presses Start. The app then
steps forward one simulated year at a time from 2026 to 2101, at about eight years
per second, and four things respond:

- **A schematic thermometer** reads the marsh soil temperature, with a dashed
  line marking where the marsh sat before the user changed anything.
- **A cartoon canister** shows methane molecules suspended in marsh sediment.
  The count is directly proportional to the modelled flux: nine at the baseline,
  so a flux ratio of 1.28 draws twelve. The readout also gives the true
  molecular flux, around 4.3 × 10¹⁵ molecules m⁻² s⁻¹ at the baseline.
- **A line chart** draws atmospheric methane concentration as the years pass,
  against a dashed reference line at the baseline concentration.
- **An impacts panel** lets the user pick a human consequence and shows its
  magnitude at the run's ending temperature. See section 6.

**Blocks two and three** are the run's two end points: a WorldWide Telescope
Earth view for the starting year and another for the ending year, each labelled
with its year and temperature. Both are centred on the marsh at 38.87° N,
76.55° W and both can be panned and zoomed independently.

### Why the globes are iframes

They have to be. The WWT engine keeps its control object in a module-level
global, `globalWWTControl`, and engine-pinia's store links exactly one instance —
`internalUnlinkFromInstance()` takes no argument. Two views cannot coexist in one
JavaScript realm. Each globe therefore loads `earth-view.html` in its own iframe,
which gives it its own realm, its own engine and its own camera. Both iframes
share one bundle, so the engine downloads once.

That page drives a raw `WWTInstance` rather than the Vue component, which buys
three things. It can boot with `startMode: "earth"`, so the engine builds its own
Blue Marble imageset. Its `ctl` is public, so the zoom-out ceiling can be raised:
the default caps the viewport at 60°, which is not enough to frame the whole disk
in a tall narrow panel, and 120° is. And it carries no Vue, pinia or Vuetify.

`public/earth.wtml` declares an Earth imageset the older store-based path needed,
and `src/composables/useEarthView.ts` is that path. Neither is used now. Both are
kept because attaching a temperature layer to the Earth frame will go through a
store like that one.

## 2. The reasoning chain, step by step

Each simulated year walks six steps. All of this lives in `src/model.ts`.

### Step 1: global anomaly to marsh temperature

```
T_marsh = T_baseline + marshAmplification × ΔT_global
```

`marshAmplification` is 1, meaning the marsh is assumed to warm exactly as fast
as the global mean. This is an assumption, not a measurement. Coastal and
mid-latitude land generally warms faster than the global average, so 1 is
conservative.

### Step 2: marsh temperature to methane flux

```
F(T) = F_baseline × Q10 ^ ((T − T_baseline) / 10)
```

This is the step where the interface is least able to lean on GCReW, and it is
the most important thing for a reviewer to understand.

**GCReW has never published a fitted temperature-response equation.** Noyce and
Megonigal (2021) report only a correlation on log-transformed flux, R² = 0.41,
p < 0.001, and state explicitly: *"We did not quantify the temperature
dependence of CH₄ production and oxidation in the present study."* Noyce et al.
(2023) do publish the form of the model they used to scale monthly chamber
measurements to annual totals:

```
ln(F) = β₀ + β₁·T_soil + β₂·DOY + β₃·(T_soil × DOY)
```

fitted separately for each plot in each year, with the day-of-year term included
because the relationship is hysteretic, flux being higher at a given temperature
in autumn than in spring. Only the per-fit RMSE and R² are published, not the β
coefficients. No observed soil-temperature time series is archived alongside the
public flux data, so the coefficients cannot be recovered from public sources
either.

So the sensitivity here is **borrowed**. We use the canonical cross-ecosystem
value, from Yvon-Durocher et al. (2014): a Boltzmann-Arrhenius activation energy
of 0.96 eV fitted to 1553 paired flux and temperature observations across 126
sites. A Q10 is not constant under an Arrhenius law, so we convert it at the
marsh's own soil temperature:

```
Q10 = exp( E · 10 / (k · T · (T + 10)) ),   k = 8.617 × 10⁻⁵ eV K⁻¹, T in kelvin
```

At 21.5 °C and 0.96 eV this gives **Q10 = 3.459**. The same conversion reproduces
the paper's own statement of a 57-fold increase from 0 to 30 °C, giving 56.6,
which is how we know the conversion is right. The published confidence interval
of 0.88 to 1.08 eV spans Q10 from 3.12 to 4.04.

Only `baselineFluxMgPerM2PerHr` in this step is a GCReW measurement.

### Step 3: one marsh to the global wetland source

```
E_wetland(T) = E_wetland_baseline × F(T) / F_baseline
```

This is the largest leap in the chain and it is deliberate. A salt marsh on its
own is climatically negligible as a methane source: global salt marsh emits about
0.26 Tg CH₄ per year (Rosentreter et al. 2023) against 159 Tg for vegetated
wetlands overall, roughly **0.16%**. Salt marsh covers 0.69% of the wetland area
in the Global Methane Budget but contributes far less than that share of the
emissions, because sulfate reduction outcompetes methanogenesis in brackish
sediment. That is the same chemistry that drives the SMARTX result.

A salt-marsh-only feedback loop would therefore be invisible and would not
survive review. Instead the model treats the marsh as the **mechanism on screen**
and applies its temperature response to the whole wetland pool. Section 7 shows
that this reproduces an independent, observationally constrained number.

Note also a definitional trap: the Global Methane Budget explicitly *excludes*
coastal vegetated ecosystems from "wetlands" on salinity grounds, so the 0.16%
above is a ratio of two independent estimates, not a partition of one total.

### Step 4: emission to atmospheric concentration

A single well-mixed box, stepped with a one-year Euler step:

```
ΔM = (E_wetland + E_other) / tgPerPpb − M / τ
```

`E_other` is every non-wetland methane source. We do not specify it: we derive it
as whatever value holds the baseline concentration exactly steady, so a starting
anomaly of zero produces a flat line rather than a slow drift. This is
`nonWetlandEmission` in the code, and it is verified in section 7.

τ is the **perturbation** lifetime of 11.8 years, not the 9.1-year total
atmospheric lifetime. The perturbation lifetime is the correct decay constant for
an emissions-driven box, because it includes the hydroxyl-radical feedback by
which added methane extends its own lifetime. Using 9.1 would under-accumulate.

### Step 5: concentration to radiative forcing

The IPCC AR6 expression, which is the Meinshausen et al. (2020) refit of Etminan
et al. (2016):

```
SARF = (a₃·√M + b₃·√N + d₃) · (√M − √M₀)
a₃ = −8.9603 × 10⁻⁵,  b₃ = −1.2462 × 10⁻⁴,  d₃ = 0.045194
M₀ = 729.2 ppb (pre-industrial CH₄),  N = 332.1 ppb N₂O, held fixed
ERF = 0.86 × SARF
```

The `b₃√N` term is the nitrous oxide band overlap; there is no separate
subtracted term. The 0.86 factor is AR6's tropospheric adjustment converting
stratospherically-adjusted forcing to effective radiative forcing, a −14%
correction specific to methane.

The model reports forcing *relative to the baseline state*, so it evaluates this
expression twice and differences the results.

### Step 6: forcing to warming, and back to step 1

```
ΔT_equilibrium = ΔT_start + feedbackExaggeration × λ × ΔERF
ΔT_global += warmingResponseRate × (ΔT_equilibrium − ΔT_global)
```

λ is the climate sensitivity parameter, 0.76 K per W m⁻². AR6 does not assess λ
directly, so this is derived as ECS divided by the forcing from doubled CO₂,
3.0 °C / 3.93 W m⁻². The transient pairing would give 0.46 instead.

`warmingResponseRate` of 0.3 per year is the one remaining placeholder in the
model. It controls only how fast the surface approaches equilibrium, not where
equilibrium is, so it changes the shape of the approach and not the final answer.

`feedbackExaggeration` multiplies **only this returning leg**. At 1 the model is
honest. Raising it makes the loop legible on screen without altering the flux
that the thermometer and canister display. If it is raised, the interface should
say so.

## 3. Every constant and its source

All of these are `PARAMS` in `src/model.ts`, and each carries its citation in a
comment there too.

| Constant | Value | Source | Kind |
| --- | --- | --- | --- |
| `baselineMarshTempC` | 21.5 °C | Ambient-plot growing-season daily means ran 20.7–22.4 °C over 2016–2019, Noyce & Megonigal 2021. 21.5 is the midpoint | measured range |
| `baselineFluxMgPerM2PerHr` | 0.32 | C3 ambient plots, 20 ± 5 µmol m⁻² h⁻¹, Mueller et al. 2020 | measured |
| `q10` | 3.459 | 0.96 eV from Yvon-Durocher et al. 2014, converted at 21.5 °C | **borrowed, not GCReW** |
| `baselineWetlandEmissionTgPerYr` | 159 | Vegetated wetlands, bottom-up, 2010–2019, range [119–203], Saunois et al. 2025 | process-model ensemble |
| `baselineCh4Ppb` | 1866.3 | 2019 concentration, AR6 WG1 Table 7.5 | observed |
| `n2oPpb` | 332.1 | 2019 concentration, AR6 WG1 Table 7.5 | observed |
| `ch4LifetimeYr` | 11.8 | Perturbation lifetime, 11.8 ± 1.8 yr, AR6 Table 7.15 | assessed |
| `tgPerPpb` | 2.75 | Prather, Holmes & Hsu 2012, as adopted by AR6 Table 6.2 | assessed |
| `climateSensitivity` | 0.76 | ECS 3.0 °C / ΔF2× 3.93 W m⁻², both AR6-assessed | **derived, not assessed** |
| `warmingResponseRate` | 0.3 | none | **PLACEHOLDER** |
| `marshAmplification` | 1.0 | none | assumption |
| `feedbackExaggeration` | 1.0 | n/a, presentation control | knob |

Two values inside the forcing code are also worth naming: the pre-industrial
methane concentration of 729.2 ppb, from AR6 WG1 Chapter 2, and the 0.86
tropospheric adjustment from AR6 §7.SM.1.3.1.

A note on one apparent inconsistency. `baselineFluxMgPerM2PerHr` is 0.32, the
published 2019 figure, while `GCREW_TREATMENTS` carries 0.280 for the same
ambient plots. The second is ours, averaged over 2017–2024 from the archived
data. They differ because they cover different years, and interannual variation
at this site is larger than the warming effect. Swap in 0.280 if you would rather
the model baseline and the plotted ambient point be identical.

## 4. The measured GCReW data

`GCREW_TREATMENTS` in `src/model.ts` holds what SMARTX actually measured. We
derived this ourselves from the archived chamber fluxes, 2424 observations across
30 plots from 2017 to 2024, released CC BY 4.0 under `doi:10.25573/serc.31581154`.
The plot-to-treatment mapping came from `github.com/abbylewis/SMARTX_CH4cast`.

Method: growing season only, May to September; ambient-CO₂ plots only; mean of
the three replicate plot means, with the standard error taken across those three
plots.

| Warming | C3 flux, µmol m⁻² d⁻¹ | C3 ratio | C4 flux, µmol m⁻² d⁻¹ | C4 ratio |
| --- | --- | --- | --- | --- |
| ambient | 419 ± 71 | 1.00 | 716 ± 175 | 1.00 |
| +1.7 °C | 487 ± 74 | 1.16 | 1011 ± 216 | 1.41 |
| +3.4 °C | 766 ± 143 | 1.83 | 976 ± 123 | 1.36 |
| +5.1 °C | 1950 ± 641 | 4.65 | 1281 ± 249 | 1.79 |

C3 is the *Schoenoplectus americanus* community, over 90% of aboveground biomass,
at lower elevation and wetter. C4 is *Spartina patens* with *Distichlis spicata*,
higher and drier. The two are separate sites within the experiment rather than a
randomised factor, so plant community and hydrology are confounded.

The experimental design is four warming levels, ambient and +1.7, +3.4 and
+5.1 °C, held year-round since 1 June 2016 by infrared heaters above the canopy
and vertical resistance cables heating soil to 1.5 m depth.

**These numbers are not plotted in the interface yet.** Drawing them as measured
points behind the smooth curve would let the app show GCReW's own data rather
than only a model of it, and would make section 5 visible on screen. That is the
change we would make next.

## 5. Where the model and the measurements disagree

This is the most interesting result in the experiment, and a single Q10 erases
it. Comparing the modelled curve against the measured ratios:

| Warming | C3 measured | C4 measured | Model |
| --- | --- | --- | --- |
| +1.7 °C | 1.16× | 1.41× | 1.23× |
| +3.4 °C | 1.83× | 1.36× | 1.52× |
| +5.1 °C | **4.65×** | 1.79× | **1.88×** |

The smooth curve tracks the C4 community tolerably. It under-predicts the C3
community at the top of the gradient by a factor of about 2.5.

The reason is biological. The C3 response is **threshold-like**: nearly flat
through +1.7 and +3.4 °C, then a sharp release at +5.1 °C. Noyce and Megonigal
attribute this to the sedge's capacity to transport oxygen into the soil, which
sustains methane oxidation until production finally overwhelms it. Deep porewater
methane in C3 plots rose from 43 to 1254 µmol L⁻¹ between ambient and +5.1 °C.
The C4 response is shallower, and in the measured data it is not even monotonic.

Fitting our own log-linear regression to the warming gradient gives:

```
C3:  ln F = 5.597 + 0.2476·ΔT    slope SE 0.0212,  R² = 0.213,  n = 504
C4:  ln F = 5.814 + 0.1238·ΔT    slope SE 0.0323,  R² = 0.030,  n = 476
```

which imply apparent per-10 °C factors of 11.9 for C3 and 3.45 for C4. **Do not
label the C3 value a Q10.** A sustained warming treatment also depletes sulfate,
changes substrate supply and shifts plant traits, so a treatment-gradient
sensitivity compounds several mechanisms and is not a thermal parameter. The
11.9 is physically implausible as a kinetic Q10. The low R² values reflect a
single ΔT term ignoring season, which is a real limitation rather than a fitting
artefact.

For completeness, the experiment also includes a +350 ppm elevated-CO₂
sub-experiment, in the C3 community only, at ambient and +5.1 °C. Elevated CO₂
*suppresses* methane, by 27% at ambient temperature and 59% under warming, via
oxygen priming. None of that is represented in this model. It also runs opposite
to the global meta-analytic mean, so it should not be generalised.

## 6. The human impacts panel

The dropdown in block one picks a human consequence and shows its magnitude at
the run's **ending** temperature, so it pairs with the label on the third block.
It is not the difference between the two globes: that difference is the methane
feedback alone, about 0.05 °C, which would show nothing.

### The baseline trap, which caught us

Every IPCC warming level is defined against **1850–1900**. The model in
`model.ts` works in anomalies above its **2019** state. Those are not the same
scale, and AR6 WG1 puts the gap at **1.09 [0.95 to 1.20] °C** for 2011–2020.

Our first pass stored anchors at 1.5, 2, 3 and 4 and fed them the model anomaly
directly, which read every curve a full degree too cold. A model anomaly of +2 is
an AR6 level of **3.09**, not 2. Anchors are now stored at their published AR6
level and converted on the way in, so the published numbers stay legible in the
source. The panel prints both scales for the same reason.

### What is in the dropdown

| Impact | At 3 °C above 1850–1900 | Source | Kind |
| --- | --- | --- | --- |
| Sea level rise | 61 cm by 2100 | AR6 WG1 Table 9.10 | published at these levels |
| Extreme heat frequency | interpolated, see below | AR6 WG1 Fig. SPM.6 | published |
| Maize yield | −14.8% | Zhao et al. 2017 | published per °C |
| Coral reefs lost | >99%, saturated | SR1.5 Ch3, AR6 WG2 Ch3 | published threshold |
| Species at extinction risk | 12% median | AR6 WG2 Ch2 §2.5.1.3 | published |
| Coastal flood exposure | 1.74× today | chained, see below | **derived** |

Values are stored at discrete warming levels and interpolated, never as a
per-degree slope, because most of these are non-linear and two are thresholds.
Coral loss saturates above 2 °C. Hot-extreme frequency roughly triples between
2 and 4 °C. Outside the anchors the value is held flat rather than extrapolated,
and the panel says so, because several of these are committed or hysteretic: sea
level, coral loss and extinction do not run backwards if the world cools.

### Three judgement calls worth challenging

**We show a hazard, not a headcount, for heat.** AR6 has no statement of the form
"X% of people exposed at Y °C". The available population numbers, from the human
climate niche literature, are driven as much by the population projection and a
no-migration assumption as by temperature. So the panel shows how much more often
a 1-in-50-year heat extreme occurs: 4.8× at 1 °C, 8.6× at 1.5, 13.9× at 2 and
39.2× at 4. AR6 publishes no 3 °C column, so that region is our interpolation.
If you would rather show people, Li, Yuan & Kopp 2020 give population exposed to
at least one day above WBGT 33 °C at 1.5, 2 and 3 °C with population held fixed,
which is the most defensible version we found.

**We show maize, not a staple average.** Averaging crops conceals the actual
result: at end-of-century high warming, maize falls about 24% while wheat *rises*
about 18%. Maize is also the best-corroborated, at −7.4%/°C from Zhao and
−7.1%/°C independently from Hasegawa et al. 2022. The Zhao sensitivity assumes no
CO₂ fertilisation, no adaptation, no genetic improvement and full irrigation, and
its linearity is the authors' own assumption; they warn a +4 °C value is likely
conservative.

**Coastal flood exposure is a multiplier, and it is derived.** Two chained steps:
AR6 sea level at each warming level, shifted 5.5 cm to move from a 1995–2014
baseline onto the 2020 baseline the exposure figures use, then fed through AR6
WG2 SPM B.4.5. That AR6 statement is a faithful restatement of Haasnoot et al.
2021, whose own published numbers are 68 million people in the 100-year
floodplain today, doubling at 0.75 m and tripling at 1.4 m.

It is a multiplier rather than a count on purpose. Present-day global population
in the 100-year floodplain ranges from 76 to 310 million across published
studies, a factor of four **at fixed climate**, driven by the digital elevation
model and the coastal-defence assumption. Across all published global estimates
of population affected by sea level rise the spread is 88 million to 1.4 billion.
Pairing our multiplier with an absolute count from a different study would be
wrong.

The sharpest evidence that the warming level is not the dominant term is Hinkel
et al. 2014, Table 4, which decomposes the sensitivity of people flooded per year
in 2100 across seven axes. Adaptation strategy moves the answer by 170 million,
the elevation model by 75 million, the socioeconomic pathway by 60 million and
the emissions scenario by 57 million. The choice of how much coastal protection
gets built matters about three times more than the emissions scenario, and the
elevation model matters more than either.

One caveat on the shape of our anchors. Haasnoot's exposure-versus-sea-level
curve accelerates, so most of the exposure arrives late. Vernimmen and Hooijer
2023, using satellite lidar rather than radar elevation data, find the opposite
curvature: exposure rises fastest in the first metre. Our interpolation follows
Haasnoot. Which way that curve bends is unsettled and depends on the elevation
data.

## 7. What we checked, and what it proved

Four independent checks, all run rather than reasoned about.

**The forcing code reproduces the published AR6 value.** Feeding 1866.3 ppb
methane and 332.1 ppb nitrous oxide through the expression gives SARF 0.6325 and
ERF **0.5440 W m⁻²**, against AR6 Table 7.5's printed 0.544. The local derivative
at that concentration comes out at 3.743 × 10⁻⁴ W m⁻² ppb⁻¹ against AR6's quoted
3.74 × 10⁻⁴.

**The wetland sensitivity matches an observational constraint.** The model gives
**19.7 Tg CH₄ per year per °C**. Zhang et al. (2026) constrain this at
**24 ± 10 Tg CH₄ per year per °C** using a seven-model ensemble tied to 163
site-years of eddy-covariance flux data. This agreement was not tuned; it falls
out of the Q10 and the wetland total. It is the best single piece of evidence
that the chain is calibrated. For contrast, Ury et al. (2025) imply roughly 44 to
81 Tg per year per °C, two to three times higher and unconstrained.

**The Q10 conversion reproduces its own source.** Our Arrhenius-to-Q10 formula
gives a 56.6-fold increase from 0 to 30 °C at 0.96 eV, against the paper's stated
57-fold, and 61.6-fold at 0.98 eV against its stated 61-fold.

**The baseline is exactly flat.** Running with a starting anomaly of zero leaves
methane at 1866.3000 ppb after 75 years, confirming that the derived non-wetland
emission term holds the box in steady state and that the dashed reference line on
the chart is honest.

We also reproduced Mueller et al. 2020's published ambient values from the
archived data as a check on our own processing: 18.9 ± 3.6 µmol m⁻² h⁻¹ for C3
against their published 20 ± 5.

## 8. Honest weaknesses

**The feedback is very small, and that is the correct answer.** With sourced
parameters and `feedbackExaggeration` at 1:

| Starting anomaly | Extra warming by 2101 | CH₄ by 2101 | Flux ratio | Molecules |
| --- | --- | --- | --- | --- |
| −2.0 °C | −0.045 °C | 1714 ppb | 0.78× | 7 |
| −1.0 °C | −0.023 °C | 1785 ppb | 0.88× | 8 |
| −0.5 °C | −0.012 °C | 1824 ppb | 0.94× | 8 |
| baseline | 0.000 °C | 1866 ppb | 1.00× | 9 |
| +1.0 °C | 0.026 °C | 1959 ppb | 1.13× | 10 |
| +1.5 °C | 0.040 °C | 2010 ppb | 1.21× | 11 |
| +2.0 °C | 0.055 °C | 2064 ppb | 1.28× | 12 |
| +3.0 °C | 0.086 °C | 2184 ppb | 1.45× | 13 |
| +4.0 °C | 0.121 °C | 2321 ppb | 1.64× | 15 |

The scenario list runs both ways. A negative starting anomaly cools the marsh,
suppresses methane production, draws the concentration down toward a lower
steady state, and gives a feedback of the opposite sign. The model is symmetric
because the Q10 response is a smooth exponential in both directions, but SMARTX
only ever warmed plots. **The cooling side is extrapolation with no measurement
behind it**, and the threshold behaviour in section 5 is good reason to doubt
that a real marsh is symmetric about its baseline.

The methane chart moves convincingly. The thermometer and the bubble count barely
budge, because a few hundredths of a degree is invisible. This is a real tension
between honesty and legibility in a visualization whose whole subject is the
feedback loop, and it is a presentation decision rather than a modelling one.

**Other known weaknesses:**

- The temperature response is a single smooth exponential, which misrepresents
  the C3 threshold as documented in section 5.
- One Q10 is applied to every wetland on Earth, tropical peatland and Arctic
  bog alike. Li et al. (2025) find the activation energy is strongly seasonal,
  peaking near 0.60 eV in early summer and falling to about zero in late winter,
  so a static value overstates summer sensitivity.
- `warmingResponseRate` is unsourced.
- The marsh is assumed to warm at exactly the global mean rate.
- Non-wetland methane sources are held fixed, so there is no anthropogenic
  emissions pathway. The user's starting anomaly is imposed, not caused.
- Nitrous oxide is held fixed at its 2019 value.
- Only the methane band is included. Ozone production and stratospheric water
  vapour from methane oxidation, worth roughly 0.47 and 0.05 W m⁻² respectively
  in the present-day budget, are omitted.
- The chart has no uncertainty band and no table view, and nothing on screen yet
  explains any of this reasoning or credits GCReW.

## 9. Two transcription traps we avoided

Both of these are easy to get wrong and both were checked numerically, so they
are recorded here in case the model is extended.

**The Etminan bracket is linear in the mean concentrations, not in their square
roots.** The correct form is

```
ΔF = (a₃·M̄ + b₃·N̄ + 0.043)·(√M − √M₀),   M̄ = ½(M+M₀),  N̄ = ½(N+N₀)
```

with a₃ = −1.3 × 10⁻⁶ and b₃ = −8.2 × 10⁻⁶ W m⁻² ppb⁻¹. The published units of
ppb⁻¹ rather than ppb⁻¹ᐟ² confirm it, and the linear form reproduces the paper's
stated 0.61 W m⁻² for 722 to 1803 ppb while the square-root version is about 9%
high. This model uses the AR6 refit rather than Etminan directly, but the same
trap applies.

**The 1.19 W m⁻² figure must not be added to 0.54.** AR6 Chapter 7 gives methane's
concentration-based ERF as 0.54 [0.43 to 0.65] W m⁻². AR6 Chapter 6 separately
gives 1.19 [0.81 to 1.58] W m⁻² as an *emissions-based attribution*, which already
bundles the lifetime feedback, ozone production, stratospheric water vapour and
aerosol effects. Adding them, or adding the ozone and water-vapour rows to the
1.19, double-counts. Use 0.54 for a concentration-driven loop like this one.

A third, smaller point: AR6 quotes three different radiative efficiencies for
methane and they are not interchangeable. 3.88 × 10⁻⁴ W m⁻² ppb⁻¹ is the pure
radiative value, 5.7 × 10⁻⁴ includes chemical adjustments and is what feeds the
global warming potentials, and 3.74 × 10⁻⁴ is the local derivative at today's
concentration. The last is the right one for a small perturbation on the present
atmosphere.

## 10. References

### GCReW and SMARTX

**Primary warming and methane result.** Noyce, G. L. & Megonigal, J. P. (2021).
Biogeochemical and plant trait mechanisms drive enhanced methane emissions in
response to whole-ecosystem warming. *Biogeosciences* 18, 2449–2463.
[doi:10.5194/bg-18-2449-2021](https://doi.org/10.5194/bg-18-2449-2021). Open
access. Source of the soil-temperature range, the R² = 0.41 correlation, the
statement that temperature dependence was not quantified, and the per-treatment
annual flux table in the supplement.

**Warming crossed with elevated CO₂.** Noyce, G. L., Smith, A. J., Kirwan, M. L.,
Rich, R. L. & Megonigal, J. P. (2023). Oxygen priming induced by elevated CO₂
reduces carbon accumulation and methane emissions in coastal wetlands. *Nature
Geoscience* 16, 63–68.
[doi:10.1038/s41561-022-01070-6](https://doi.org/10.1038/s41561-022-01070-6).
Source of the published log-linear scaling model form and the elevated-CO₂
suppression percentages.

**Experimental design and heating system.** Noyce, G. L., Kirwan, M. L., Rich,
R. L. & Megonigal, J. P. (2019). *PNAS* 116, 21623–21628.
[doi:10.1073/pnas.1904990116](https://doi.org/10.1073/pnas.1904990116). Source
of the warming levels and the heating method.

**Ambient fluxes in hourly units.** Mueller, P., Mozdzer, T. J., Langley, J. A.,
Aoki, L. R., Noyce, G. L. & Megonigal, J. P. (2020). Plant species determine
tidal wetland methane response to sea level rise. *Nature Communications* 11,
5154.
[doi:10.1038/s41467-020-18763-4](https://doi.org/10.1038/s41467-020-18763-4).
Source of `baselineFluxMgPerM2PerHr`.

**Microbial mechanism.** Lee, J., Yang, Y., Kang, H., Noyce, G. L. & Megonigal,
J. P. (2025). Climate-induced shifts in sulfate dynamics regulate anaerobic
methane oxidation in a coastal wetland. *Science Advances* 11(17), eads6093.
[doi:10.1126/sciadv.ads6093](https://doi.org/10.1126/sciadv.ads6093).

**Eight-year record and the public dataset.** Lewis, A. S. L., Holmquist, J. R.,
Al-Haj, A. N., Read, Z. N., Rich, R. L., Megonigal, J. P. & Noyce, G. L. (2026).
Warming decreases the predictability of methane emissions in a coastal wetland.
*Ecosphere* 17(5).
[doi:10.1002/ecs2.70647](https://doi.org/10.1002/ecs2.70647). The dataset behind
`GCREW_TREATMENTS`: [doi:10.25573/serc.31581154](https://doi.org/10.25573/serc.31581154),
CC BY 4.0, with plot metadata at
[github.com/abbylewis/SMARTX_CH4cast](https://github.com/abbylewis/SMARTX_CH4cast).

### Temperature dependence of methane flux

**The activation energy we use.** Yvon-Durocher, G., Allen, A. P., Bastviken, D.,
Conrad, R., Gudasz, C., St-Pierre, A., Thanh-Duc, N. & del Giorgio, P. A. (2014).
Methane fluxes show consistent temperature dependence across microbial to
ecosystem scales. *Nature* 507, 488–491.
[doi:10.1038/nature13164](https://doi.org/10.1038/nature13164). Note a
discrepancy between versions: the published paper gives 0.96 eV and a 57-fold
increase over 0 to 30 °C, while the accepted manuscript gives 0.98 eV, a 61-fold
increase, and a 95% confidence interval of 0.88 to 1.08 eV. Each is internally
consistent. The confidence interval we can verify belongs to the 0.98 value.

**Seasonality caveat.** Li, H. et al. (2025). *Functional Ecology*.
[doi:10.1111/1365-2435.70127](https://doi.org/10.1111/1365-2435.70127). Refits
FLUXNET-CH4 by season and finds activation energy peaking near 0.60 eV in early
summer, well below 0.96.

**Component Q10 values cited by Noyce.** Segers, R. (1998). *Biogeochemistry* 41,
23–51. Methanogenesis Q10 of 4.1 and aerobic methane oxidation Q10 of 1.9. The
gap between them is the mechanism Noyce and Megonigal invoke.

### Global budgets and scaling

**Global Methane Budget.** Saunois, M. et al. (2025). Global Methane Budget
2000–2020. *Earth System Science Data* 17, 1873–1958.
[doi:10.5194/essd-17-1873-2025](https://doi.org/10.5194/essd-17-1873-2025).
Source of the 159 Tg vegetated-wetland total. Note the bracketed ranges in that
paper are ensemble minima and maxima, not confidence intervals, and that the
budget excludes salt marsh from its wetland definition.

**Salt marsh methane.** Rosentreter, J. A. et al. (2023). Coastal vegetation and
estuaries are collectively a greenhouse gas sink. *Nature Climate Change* 13,
579–587.
[doi:10.1038/s41558-023-01682-9](https://doi.org/10.1038/s41558-023-01682-9).
Salt marsh at 0.26 Tg CH₄ per year over 54,550 km². Be aware that earlier
estimates using means rather than medians on a strongly right-skewed distribution
are up to an order of magnitude higher, for example Rosentreter et al. (2021),
*Nature Geoscience* 14, 225–230,
[doi:10.1038/s41561-021-00715-2](https://doi.org/10.1038/s41561-021-00715-2),
whose median is 0.18 but whose mean is 2.00 ± 1.51.

**Salt marsh area.** McOwen, C. J. et al. (2017). *Biodiversity Data Journal* 5,
e11764. [doi:10.3897/BDJ.5.e11764](https://doi.org/10.3897/BDJ.5.e11764).

**Tidal marsh context.** Arias-Ortiz, A. et al. (2024). *Global Change Biology*
30, e17462. [doi:10.1111/gcb.17462](https://doi.org/10.1111/gcb.17462). CONUS
tidal marshes average 26 ± 53 g CH₄ m⁻² yr⁻¹ with a median of 3.9, so SMARTX
ambient sits at or below the national median.

### Closing the loop

**The observational constraint we validate against.** Zhang, Z. et al. (2026).
*Nature Geoscience*.
[doi:10.1038/s41561-026-01987-2](https://doi.org/10.1038/s41561-026-01987-2).
24 ± 10 Tg CH₄ per year per °C of global land-surface warming, from a seven-model
ensemble constrained by 163 site-years of eddy covariance.

**A less-constrained alternative.** Ury, E. A., Zhang, Z. & Buma, B. (2025).
*Nature Sustainability* 8, 1115–1118.
[doi:10.1038/s41893-025-01625-6](https://doi.org/10.1038/s41893-025-01625-6).
Implies roughly 44 to 81 Tg per year per °C, two to three times higher.

**Earlier feedback estimate.** Zhang, Z. et al. (2017). *PNAS* 114, 9647–9652.
Wetland methane feedback parameter of 0.03 ± 0.001 W m⁻² K⁻¹, worth 0.04 to
0.12 °C of extra warming by 2100.

### Radiative forcing and climate sensitivity

**The assessment we follow.** IPCC (2021). *Climate Change 2021: The Physical
Science Basis*, Working Group I contribution to the Sixth Assessment Report.
Chapter 7 and its supplementary material. Specifically Table 7.SM.1 for the
forcing coefficients, §7.SM.1.3.1 for the 0.86 tropospheric adjustment, Table 7.5
for concentrations and present-day forcing, Table 7.15 for the perturbation
lifetime and global warming potentials, and Chapter 2 for pre-industrial
concentrations. Chapter 6 Table 6.2 for the mass-to-mixing-ratio conversion.

**The forcing expression's origin.** Etminan, M., Myhre, G., Highwood, E. J. &
Shine, K. P. (2016). Radiative forcing of carbon dioxide, methane, and nitrous
oxide: a significant revision of the methane radiative forcing. *Geophysical
Research Letters* 43, 12614–12623.
[doi:10.1002/2016GL071930](https://doi.org/10.1002/2016GL071930). Refit by
Meinshausen, M. et al. (2020), *Geoscientific Model Development* 13, 3571–3605,
[doi:10.5194/gmd-13-3571-2020](https://doi.org/10.5194/gmd-13-3571-2020), which
is the version AR6 tabulates and which this model implements.

**Mass to mixing ratio.** Prather, M. J., Holmes, C. D. & Hsu, J. (2012).
*Geophysical Research Letters* 39, L09803.
[doi:10.1029/2012GL051440](https://doi.org/10.1029/2012GL051440). 2.75 Tg CH₄ per
ppb. The value 2.78 that circulates is not an AR6 number.

**The superseded expression**, for anyone comparing against older work: Myhre,
G., Highwood, E. J., Shine, K. P. & Stordal, F. (1998). *Geophysical Research
Letters* 25, 2715–2718. This is the origin of the α = 0.036 W m⁻² ppb⁻¹ᐟ²
square-root form used through AR5.

### Human impacts

**Sea level rise.** AR6 WG1 Chapter 9, Table 9.10, which is indexed by warming
level rather than by scenario. Note AR6's own caveat that projections by warming
level are only interpretable alongside a time frame, because sea level tracks
time-integrated temperature, and that above 3 °C there is deep uncertainty.

**Extreme heat frequency.** AR6 WG1 Figure SPM.6, for a hot extreme that occurred
once in 50 years in a climate without human influence.

**Maize yield.** Zhao, C. et al. (2017). *PNAS* 114, 9326–9331.
[doi:10.1073/pnas.1701762114](https://doi.org/10.1073/pnas.1701762114). −7.4 ±
4.5% per °C. Corroborated independently at −7.1%/°C by Hasegawa, T. et al. (2022),
*Scientific Data* 9, 58,
[doi:10.1038/s41597-022-01150-7](https://doi.org/10.1038/s41597-022-01150-7).
The opposite-sign wheat result is Jägermeyr, J. et al. (2021), *Nature Food* 2,
873–885,
[doi:10.1038/s43016-021-00400-y](https://doi.org/10.1038/s43016-021-00400-y).

**Coral reef loss.** IPCC SR1.5 Chapter 3 §3.4.4 and AR6 WG2 Chapter 3. Primary
sources Frieler, K. et al. (2013), *Nature Climate Change* 3, 165–170,
[doi:10.1038/nclimate1674](https://doi.org/10.1038/nclimate1674), and
Schleussner, C.-F. et al. (2016), *Earth System Dynamics* 7, 327–351,
[doi:10.5194/esd-7-327-2016](https://doi.org/10.5194/esd-7-327-2016). Worth a
footnote if this is presented: Klein, S. G., Roch, C. & Duarte, C. M. (2024),
*Nature Communications* 15,
[doi:10.1038/s41467-024-46255-2](https://doi.org/10.1038/s41467-024-46255-2),
finds the "excess heat" model family behind these figures is a third of the
studies but two thirds of the citations, and may project more severe outcomes
than other methods.

**Species at extinction risk.** AR6 WG2 Chapter 2 §2.5.1.3, medians. The matching
maximum likely range is 14/18/29/39/48%. Note AR6 Figure 2.7 is not independent
of Urban, M. C. (2015), *Science* 348, 571–573,
[doi:10.1126/science.aaa4984](https://doi.org/10.1126/science.aaa4984): 126 of its
178 estimates are digitised from that paper, so the two are not corroborating
lines of evidence.

**Coastal flood exposure.** AR6 WG2 SPM B.4.5, from Haasnoot, M. et al. (2021),
*Climate Risk Management* 34, 100355,
[doi:10.1016/j.crm.2021.100355](https://doi.org/10.1016/j.crm.2021.100355).
The disagreement on present-day exposure is Kulp, S. A. & Strauss, B. H. (2019),
*Nature Communications* 10, 4844,
[doi:10.1038/s41467-019-12808-z](https://doi.org/10.1038/s41467-019-12808-z),
and Muis, S. et al. (2016), *Nature Communications* 7, 11969,
[doi:10.1038/ncomms11969](https://doi.org/10.1038/ncomms11969). The 88 million
to 1.4 billion spread across all published estimates is Hauer, M. E. et al.
(2021), *Nature Communications* 12, 6900,
[doi:10.1038/s41467-021-27260-1](https://doi.org/10.1038/s41467-021-27260-1).

**The sensitivity decomposition.** Hinkel, J. et al. (2014). *PNAS* 111,
3292–3297.
[doi:10.1073/pnas.1222469111](https://doi.org/10.1073/pnas.1222469111), Table 4.
The counter-curvature result is Vernimmen, R. & Hooijer, A. (2023), *Earth's
Future* 11, e2022EF002880,
[doi:10.1029/2022EF002880](https://doi.org/10.1029/2022EF002880); its abstract
was verified but not its body numbers.

**The baseline offset.** AR6 WG1 SPM A.1.2: 1.09 [0.95 to 1.20] °C for 2011–2020
relative to 1850–1900.

**The heat-exposure numbers we rejected**, so the decision in section 6 can be
checked: Xu, C., Kohler, T. A., Lenton, T. M., Svenning, J.-C. & Scheffer, M.
(2020). *PNAS* 117, 11350–11355.
[doi:10.1073/pnas.1910114117](https://doi.org/10.1073/pnas.1910114117), which
projects a third of the global population experiencing a mean annual temperature
above 29 °C, assuming RCP8.5, an SSP3 population and explicitly no migration. And
Lenton, T. M. et al. (2023). *Nature Sustainability* 6, 1237–1247.
[doi:10.1038/s41893-023-01132-6](https://doi.org/10.1038/s41893-023-01132-6),
which puts 21 to 42% of a projected 9.5 billion people outside the human climate
niche at about 2.7 °C. Both are defensible papers; the objection is that the
percentage moves with the population projection and the migration assumption as
much as with temperature, which makes them a poor fit for a temperature dial.

**If you do want a population-based heat metric**, the most defensible we found is
Li, D., Yuan, J. & Kopp, R. E. (2020), *Environmental Research Letters* 15,
064003,
[doi:10.1088/1748-9326/ab7d04](https://doi.org/10.1088/1748-9326/ab7d04), which
gives population exposed to at least one day above WBGT 33 °C at 1.5, 2 and 3 °C
with the population distribution held fixed. Only its abstract was verified.

### Not publicly available

Recorded so nobody repeats the search:

- Any fitted temperature-response coefficient, Q10 or activation energy specific
  to SMARTX. Only the model form and per-fit R² values are published.
- An observed soil-temperature time series for SMARTX, which is why the
  published regression coefficients cannot be recovered.
- Absolute per-treatment fluxes for +1.7 and +3.4 °C in the 2021 and 2023 papers,
  which appear in figures only.
- A confidence interval attached specifically to the published 0.96 eV value.

## 11. Code map and known gaps

| What | Where |
| --- | --- |
| The model, every constant, and every citation | `src/model.ts` |
| The measured GCReW treatment points | `GCREW_TREATMENTS` in `src/model.ts` |
| Impact anchors, sources, and the baseline offset | `src/impacts.ts` |
| Three-block layout and the year-by-year loop | `src/MarshMethane.vue` |
| The globe that runs inside each iframe | `src/earth-view.ts`, `earth-view.html` |
| The iframe wrapper and its year/temperature label | `src/components/EarthPanel.vue` |
| Thermometer, canister, chart, controls, impacts | `src/components/` |
| Unused, kept for the future temperature layer | `src/composables/useEarthView.ts`, `public/earth.wtml` |

The two pages are declared in `vite.config.mts`, which also explains why there
are two.

**Next steps, roughly in order of value:**

1. Plot `GCREW_TREATMENTS` as measured points behind the smooth curve, so the
   C3 threshold from section 5 is visible and the app shows real data.
2. Put text on screen explaining the chain and crediting GCReW. Right now none
   of this document reaches the user.
3. Replace the schematic thermometer with a real temperature layer on the globe.
   `createTableLayer` accepts `referenceFrame: "Earth"`, so a gridded field can
   be attached to the Earth frame rather than the sky. No other project in
   `cosmicds-wwt-vue` has done Earth view, which is why `public/earth.wtml`
   exists here.
4. Let the user pick the plant community, so the C3 and C4 contrast becomes
   part of the story rather than something averaged away.
5. Add an uncertainty band from the 0.88 to 1.08 eV activation-energy interval,
   and a table view of the chart.
