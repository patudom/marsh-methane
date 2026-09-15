# Claude in progress notes group 1

Both background agents have reported, and I independently cross-checked their key coefficients against the FaIR reference implementation and the Saunois 2025 PDF.

1. Published functional form — there isn't a fitted equation with coefficients
This is the most important finding, and it's a negative one. No SMARTX paper publishes a temperature-response equation with fitted coefficients. What is published:

- Noyce & Megonigal 2021 (Biogeosciences) reports only a correlation: "Methane emissions increased with soil temperature (R² = 0.41, p < 0.001)" (their Fig. 1). Methods state CH₄ flux was log-transformed and tested with Pearson's correlations — so it is effectively a log-linear (exponential) relationship, but no slope/intercept is given.

- Noyce et al. 2023 (Nature Geoscience) Methods give the actual model form used for annual scaling: "Monthly CH₄ flux measurements were scaled to annual estimates by regressing log CH₄ emissions against daily mean soil temperature and day of year as a proxy for phenological status... Individual linear regressions were calculated for each plot and year." Supplementary Fig. 1 confirms the predictors are day-of-year, daily soil temperature, and their interaction:

ln(F_CH4) = b0 + b1·T_soil + b2·DOY + b3·(T_soil × DOY)

They note the relationship is hysteretic — flux is higher at a given temperature in autumn than spring, which is why DOY is in the model. Supplementary Table 1 reports only RMSE and R² per plot-year (R² ranges 0.03–1.00, mostly 0.65–0.96). The 96 fitted coefficient sets are not published.

- No Q10 or activation energy was measured at this site. Noyce & Megonigal 2021 state explicitly: "We did not quantify the temperature dependence of CH₄ production and oxidation in the present study."

- Lewis et al. 2026 (Ecosphere) uses 10 purely statistical/ML forecast models (ETS, auto.arima, prophet, XGBoost, randomForest, SVM, elasticNet, BRNN, rEDM, climatology — confirmed from their code repo github.com/abbylewis/SMARTX_CH4cast). No mechanistic Q10 model.

Also: no observed soil-temperature time series is publicly archived alongside the SMARTX flux data (the only met file in their repo is ECMWF forecast temperature), so the exponential coefficients cannot be refit from public data.

2. Q10 / activation energy
Values cited by the SMARTX papers, all from other literature:

- Methanogenesis Q10 = 4.1; aerobic CH₄ oxidation Q10 = 1.9 — from Segers (1998), Biogeochemistry 41:23–51. No uncertainty given in Noyce & Megonigal's citation. This differential is mechanism (i) of their four proposed mechanisms.
The canonical published number with uncertainty (cited by Noyce 2021, and what I'd actually use for a visualization) is Yvon-Durocher et al. 2014, Nature 507:488–491, doi:10.1038/nature13164. Boltzmann–Arrhenius mixed-effects form, their Eq. 1:

ln F_i(T) = (E_M + ε_EM,i)·(1/kT_C − 1/kT) + (ln F(T_C) + ε_F,i)   with k = 8.617×10⁻⁵ eV K⁻¹

Level	E_M (eV)	95% CI	n
Methanogen cultures	1.10	0.93–1.27	118, 33 units
Anaerobic slurries (community)	0.93	0.82–1.03	402, 47 units
Ecosystem-scale seasonal CH₄ emission	0.96 (published) / 0.98 (accepted MS)	0.88–1.08	1553 obs, 126 sites
CH₄:CO₂ flux ratio	0.71	0.46–0.97	177, 38 sites
Respiration (for contrast)	~0.65	—	—
Caveat: the published Nature version says 0.96 eV / 57-fold increase 0–30 °C; the open-access accepted manuscript says 0.98 eV / 61-fold with CI 0.88–1.08. I verified the arithmetic: 0.96 eV gives exactly 56.6-fold over 0–30 °C, so the CI I can quote (0.88–1.08) belongs to the 0.98 eV value.

My Q10 conversions (Q10 = exp[E·10/(k·T·(T+10))]):

E_M	Q10 @10 °C	@15 °C	@20 °C	@25 °C
0.96 eV	3.83	3.66	3.50	3.36
0.88 eV	3.42	3.28	3.16	3.04
1.08 eV	4.53	4.30	4.10	3.91
A more recent and much lower estimate: Li et al. 2025, Functional Ecology, doi:10.1111/1365-2435.70127 — FLUXNET-CH4 analysis finds seasonally varying E_M peaking at 0.60 eV in early summer and −0.02 eV in late winter. Worth knowing that 0.96 eV is contested.

3–4. Warming treatments, measured fluxes, baseline
Design (Noyce & Megonigal 2021; Noyce et al. 2019 PNAS): GCReW / Kirkpatrick Marsh, Edgewater MD, 38°53′N 76°33′W. Started 1 June 2016, year-round. Six transects (3 per plant community), each an active gradient of ambient, +1.7, +3.4, +5.1 °C. 2 m × 2 m plots; IR heaters above canopy, vertical resistance cables to 1.5 m depth; feedback-controlled. Monthly static-chamber fluxes (stackable 40 cm chambers, LGR UGGA then LI-7810).

Published annual estimates (Noyce & Megonigal 2021, Table S2, mmol CH₄ m⁻² yr⁻¹, mean ± SE of 3 plots):

2017	2018	2019
C3 ambient	58.4 (6.9)	161.4 (37.0)	80.4 (11.4)
C3 +1.7	69.2 (21.8)	189.2 (23.0)	82.1 (6.5)
C3 +3.4	82.6 (12.2)	178.8 (21.5)	90.7 (13.4)
C3 +5.1	178.0 (78.2)	343.2 (140.0)	317.6 (174.5)
C4 ambient	55.0 (6.9)	425.5 (88.6)	205.1 (45.2)
C4 +1.7	61.7 (12.3)	370.9 (73.7)	417.6 (156.1)
C4 +3.4	84.8 (24.5)	471.0 (96.9)	386.8 (127.6)
C4 +5.1	157.8 (37.1)	879.3 (328.9)	469.9 (175.2)
⚠️ The abstract's headline "58 → 343" (C3) and "55 → 879" (C4) mixes years — those are 2017 ambient vs 2018 +5.1 °C. Within-year ratios are smaller. 3-year means: C3 100 → 280; C4 229 → 502 mmol m⁻² yr⁻¹ (× 0.016043 for g CH₄ m⁻² yr⁻¹ → C3 1.6 → 4.5; C4 3.7 → 8.1).

Published growing-season aggregate: 5.1 °C warming took emissions from 624 → 1413 µmol CH₄ m⁻² d⁻¹ (p_adj = 0.02), pooling both communities and 4 years.

Baseline / ambient, in hourly units — Mueller et al. 2020 Nat. Commun. 11:5154 reports SMARTX ambient growing-season means: C4 (Spartina) 65 ± 37 and C3 (Schoenoplectus) 20 ± 5 µmol m⁻² h⁻¹. I reproduced this from the public data (2019 Jun–Sep, ambient plots only, plot-level means): C3 18.9 ± 3.6, C4 49.0 ± 12.8 µmol m⁻² h⁻¹ — C3 matches well, C4 is lower than published. Converted: 20 µmol m⁻² h⁻¹ = 0.32 mg CH₄ m⁻² h⁻¹ = 5.6 nmol m⁻² s⁻¹.

Measured values I derived from the archived 8-year dataset (Lewis et al. 2026 data, figshare doi:10.25573/serc.31581154, CC BY 4.0; direct CSV: https://ndownloader.figshare.com/files/62545555; local copy at /private/tmp/claude-501/-Users-Pat-Documents-GitHub-marsh-methane/01e5fe52-d677-495a-b95c-281ec95a6831/scratchpad/smartx_ch4_2017_2024.csv). Plot→treatment mapping validated against their Raw_data/plot_treatments.csv. Growing season (May–Sep), 2017–2024, plot-level means then treatment mean ± SE (n = 3 plots):

Treatment	µmol m⁻² d⁻¹	SE	mg CH₄ m⁻² h⁻¹	nmol m⁻² s⁻¹	ratio to ambient
C3 ambient	419	71	0.280	4.85	1.00
C3 +1.7	487	74	0.325	5.63	1.16
C3 +3.4	766	143	0.512	8.86	1.83
C3 +5.1	1950	641	1.303	22.57	4.57
C4 ambient	716	175	0.478	8.28	1.00
C4 +1.7	1011	216	0.676	11.70	1.41
C4 +3.4	976	123	0.652	11.29	1.36
C4 +5.1	1281	249	0.856	14.82	1.78
C3 ambient + eCO₂	311	40	0.208	3.61	—
C3 +5.1 + eCO₂	1147	256	0.767	13.27	—
The C3 4.57× corroborates SERC's press statement that sedge-dominated plots "rose nearly four times higher."

My log-linear fit across the warming gradient (growing season, positive fluxes, ambient-CO₂ plots, individual observations):

C3: ln F = 5.597 + 0.2476·ΔT, slope SE 0.0212, R² = 0.213, n = 504 → apparent multiplier-per-10 °C = 11.9 [7.9–18.0]
C4: ln F = 5.814 + 0.1238·ΔT, slope SE 0.0323, R² = 0.030, n = 476 → 3.45 [1.8–6.5]
This is not a thermodynamic Q10 and I'd label it that way in any figure. A whole-ecosystem warming treatment also changes substrate supply, sulfate depletion, and plant traits, so the treatment-gradient sensitivity is inflated relative to a seasonal Arrhenius response. For a feedback prototype: use E_M = 0.96 eV (Q10 ≈ 3.5) for the seasonal temperature term, and the measured treatment multipliers (1.16×, 1.83×, 4.57× for C3) as the observed whole-ecosystem warming response.

5. Citations
- Noyce, G. L. & Megonigal, J. P. (2021). Biogeochemical and plant trait mechanisms drive enhanced methane emissions in response to whole-ecosystem warming. Biogeosciences 18, 2449–2463. doi:10.5194/bg-18-2449-2021 — the primary warming–methane paper.
- Noyce, G. L., Smith, A. J., Kirwan, M. L., Rich, R. L. & Megonigal, J. P. (2023). Oxygen priming induced by elevated CO₂ reduces carbon accumulation and methane emissions in coastal wetlands. Nature Geoscience 16, 63–68. doi:10.1038/s41561-022-01070-6 — warming × eCO₂.
- Lee, J., Yang, Y., Kang, H., Noyce, G. L. & Megonigal, J. P. (2025). Climate-induced shifts in sulfate dynamics regulate anaerobic methane oxidation in a coastal wetland. Science Advances 11(17), eads6093. doi:10.1126/sciadv.ads6093 — the "microbes struggle to keep up" paper.
- Lewis, A. S. L., Holmquist, J. R., Al-Haj, A. N., Read, Z. N., Rich, R. L., Megonigal, J. P. & Noyce, G. L. (2026). Warming decreases the predictability of methane emissions in a coastal wetland. Ecosphere 17(5). doi:10.1002/ecs2.70647 — 8-year dataset; 5× higher forecast error at +5.1 °C.
Mueller, P., Mozdzer, T. J., Langley, J. A., Aoki, L. R., Noyce, G. L. & Megonigal, J. P. (2020). Plant species determine tidal wetland methane response to sea level rise. Nat. Commun. 11, 5154. doi:10.1038/s41467-020-18763-4
- Noyce, G. L., Kirwan, M. L., Rich, R. L. & Megonigal, J. P. (2019). PNAS 116, 21623–21628. doi:10.1073/pnas.1904990116 — experimental design/heating system.
- Yvon-Durocher et al. 2014, Nature 507:488–491, doi:10.1038/nature13164 (temperature dependence).
- Context: Arias-Ortiz et al. 2024, GCB 30:e17462, doi:10.1111/gcb.17462 — 100 chamber + 9 EC sites, CONUS tidal marshes: 26 ± 53 g CH₄ m⁻² yr⁻¹ mean, median 3.9. SMARTX ambient (1.6–3.7 g m⁻² yr⁻¹) sits below that median, as expected for a brackish site.

6. Plant community and elevated CO₂ — yes, both, and both change the response
Plant community (C3 Schoenoplectus americanus, >90% of aboveground biomass, wetter/lower elevation; vs C4 Spartina patens + Distichlis spicata, 56–76%, drier/higher elevation):

- C4 emits more than C3 under ambient (F₁,₂₂ = 13.6, p = 0.001 growing season; F₁,₂₂ = 8.5, p = 0.008 annual) — roughly 2× ambient, >3× under +1.7 to +3.4 °C.
- The shape of the warming response differs. C3 is flat through +1.7/+3.4 then jumps sharply at +5.1; C4 responds more gradually. Their mechanism: "the relatively high capacity of Schoenoplectus to transport O₂ held the CH₄ emissions stimulation caused by modest levels of warming (+1.7 to +3.4 °C) to rates similar to under ambient conditions... At high warming (+5.1 °C), however, Schoenoplectus community CH₄ emissions drastically increase." My derived slopes quantify this: C3 0.2476 vs C4 0.1238 per °C — a 2× difference in temperature sensitivity between plant communities. Lewis et al. 2026 independently find warming degrades forecastability more in C3 plots.
- Deep porewater CH₄ moves in opposite directions: warming raised it in C3 (43 → 1254 µmol L⁻¹ at +5.1 °C) but lowered it in C4 (155 → 40).

Elevated CO₂ — a crossed sub-experiment, +350 ppm, in the C3 community only (6 plots: ambient and +5.1 °C, ± eCO₂; confirmed from their plot metadata — there are no C4 eCO₂ plots).

- Warming alone: +317% summer CH₄ at +5.1 °C (p < 0.001), and +141% porewater CH₄.
- eCO₂ suppresses it: −27% at ambient temperature (p = 0.017), −59% under +5.1 °C (p = 0.008). Warmed + eCO₂ plots were not significantly above ambient-temperature plots (p = 0.171).
- Mechanism: eCO₂ increases plant-mediated O₂ flux ("oxygen priming"), raising soil redox; Lee et al. 2025 add that eCO₂ raises porewater SO₄²⁻ and stimulates sulfate-dependent anaerobic methane oxidation (S-DAMO: 0.905 → 4.194 nmol ¹³CO₂ g⁻¹ d⁻¹ in C3), while warming depletes SO₄²⁻ and suppresses it (→ 0.195). S-DAMO removes 7% (C3) and 12% (C4) of CH₄ produced.
- Note eCO₂ did not reduce net radiative forcing — the CH₄ saving was offset by lost soil carbon sequestration (p = 0.582). They use a sustained-flux GWP₁₀₀ of 45 (Neubauer & Megonigal 2015, Ecosystems 18:1000–1013, doi:10.1007/s10021-015-9879-4).
- ⚠️ SMARTX's eCO₂ suppression runs counter to the global meta-analysis: Chen et al. 2025, GCB 31, doi:10.1111/gcb.70325 finds eCO₂ has no significant effect on natural wetland CH₄ (and +18.6% in paddies), warming +26.7% in natural wetlands.


7. CH₄ → radiative forcing → temperature
AR6's operative formula (Meinshausen et al. 2020 fit, AR6 Table 7.SM.1):

SARF_CH4 = (a₃√M + b₃√N + d₃)(√M − √M₀), with a₃ = −8.9603×10⁻⁵, b₃ = −1.2462×10⁻⁴, d₃ = 0.045194, M₀ = 731.41 ppb. N₂O overlap is the b₃√N term.

ERF_CH4 = 0.86 × SARF_CH4 — AR6 applies a −14% tropospheric adjustment for CH₄, using Chapter 2 baselines C₀ = 278.3 ppm, N₀ = 270.1 ppb, M₀ = 729.2 ppb (not the 731.41 in the fit). Verified: M = 1866.3, N = 332.1 → SARF 0.6325, × 0.86 = 0.5440 W m⁻², matching AR6 Table 7.5's published 0.544 exactly.

Etminan et al. 2016 (doi:10.1002/2016GL071930), Table 1 — and one correction to your prompt:

ΔF_CH4 = (a₃·M̄ + b₃·N̄ + 0.043)(√M − √M₀), a₃ = −1.3×10⁻⁶, b₃ = −8.2×10⁻⁶ W m⁻² ppb⁻¹, M̄ = ½(M+M₀), N̄ = ½(N+N₀).

The bracket is linear in M̄ and N̄, not √M̄ and √N̄. The form in your request is a common mis-transcription. Verified two ways: the linear form reproduces the paper's stated 0.61 W m⁻² for 722→1803 ppb, whereas the √ form gives 0.668 (9% off); and I independently confirmed the linear form in the FaIR reference implementation (src/fair/forcing/ghg.py: (a3 * 0.5*(ch4+ch4_base) + b3 * 0.5*(n2o+n2o_base) + d3) * (sqrt(ch4) - sqrt(ch4_base))). Printed units (ppb⁻¹, not ppb⁻¹ᐟ²) confirm it.

Older TAR/AR4/AR5 form (Myhre et al. 1998; AR5 Table 8.SM.1): ΔF = α(√M − √M₀) − [f(M,N₀) − f(M₀,N₀)] with α = 0.036 W m⁻² ppb⁻¹ᐟ² and f(M,N) = 0.47·ln[1 + 2.01×10⁻⁵(MN)^0.75 + 5.31×10⁻¹⁵M(MN)^1.52]. Verified: 722→1803 ppb at N = 324 gives 0.4844, matching AR5's 0.48.

AR6 assessed ERF and concentrations (Table 7.5):

1750	2019	ERF 1750→2019
CH₄	729.2 ppb	1866.3 ppb	0.544 ± 0.109 W m⁻², ExecSum 0.54 [0.43–0.65]
N₂O	270.1 ppb	332.1 ppb	0.208 ± 0.031
CO₂	278.3 ppm	409.9 ppm	2.156 ± 0.259
Plus ozone 0.47 [0.24–0.71] and stratospheric H₂O from CH₄ oxidation 0.05 [0.00–0.10] W m⁻².

⚠️ The ~1.19 W m⁻² figure is from Chapter 6, not Chapter 7, and is an emissions-based attribution: 1.19 [0.81–1.58] W m⁻² attributed to CH₄ emissions, bundling lifetime feedback, ozone production, stratospheric H₂O and aerosol effects. Do not add it to 0.54 or to the ozone/strat-H₂O rows — that double-counts.

Climate sensitivity parameter λ — AR6 does not assess λ directly. Assessed inputs: ΔF₂ₓCO₂ = 3.93 ± 0.47 W m⁻²; ECS = 3.0 °C (likely 2.5–4.0, very likely 2.0–5.0); TCR = 1.8 °C (likely 1.4–2.2); net feedback α = −1.16 W m⁻² °C⁻¹ (likely −1.54 to −0.78). Derived:

Route	λ (K per W m⁻²)
ECS / ΔF₂ₓ = 3.0/3.93	0.763 (0.64–1.02)
−1/α = 1/1.16	0.862 (0.65–1.28)
TCR / ΔF₂ₓ = 1.8/3.93	0.458 (0.36–0.56)
The 0.76 vs 0.86 gap is an acknowledged AR6 inconsistency (ECS was assessed from multiple lines of evidence, not from α). For a linear ΔT = λ·ΔF, λ_eq ≈ 0.76 and λ_tcr ≈ 0.46 are the internally consistent pairings.

GWP / radiative efficiency (AR6 Table 7.15): CH₄ non-fossil GWP₁₀₀ = 27.0 ± 11, GWP₂₀ = 79.7 ± 25.8; fossil CH₄ GWP₁₀₀ = 29.8 ± 11, GWP₂₀ = 82.5 ± 25.8. Perturbation lifetime 11.8 ± 1.8 yr.

⚠️ Three different "radiative efficiency of CH₄" appear in AR6 and are not interchangeable: 3.88×10⁻⁴ W m⁻² ppb⁻¹ (pure radiative, Table 7.SM.7); 5.7×10⁻⁴ ± 1.4×10⁻⁴ (with ozone + strat-H₂O chemical adjustments, Table 7.15, used for GWP); and 3.74×10⁻⁴ (local dERF/dM at 1866.3 ppb, derived from the concentration formula — this is the right one for a small perturbation on today's atmosphere, scaled by ~1.47 if you want chemical adjustments).

Tg → ppb: 2.75 Tg CH₄ per ppb (0.3636 ppb/Tg), from Prather, Holmes & Hsu 2012, GRL 39:L09803, doi:10.1029/2012GL051440 — cited in AR6 Ch.6 Table 6.2 caption and in both Saunois budgets. I independently confirmed the 2.75 citation in the Saunois 2025 PDF. 2.78 is not an AR6 number and no authoritative source was found for it.

Lifetimes (AR6 Ch.6 Table 6.2) — the distinction matters: total atmospheric lifetime 9.1 ± 0.9 yr; OH feedback factor 1.30 ± 0.07; perturbation lifetime 11.8 ± 1.8 yr (this is what's in Table 7.15 and what an emissions-driven box model needs). The 12.4 ± 1.4 yr you mentioned is the AR5 perturbation lifetime, superseded.

8. Global wetland and salt marsh totals
Global Methane Budget 2000–2020 — Saunois et al. 2025, ESSD 17:1873–1958, doi:10.5194/essd-17-1873-2025. All Tg CH₄ yr⁻¹, brackets are [min–max] of the model ensemble, not CIs. 2010–2019:

Bottom-up	Top-down
Total sources	669 [512–849]	575 [553–586]
Wetlands + inland freshwaters	248 [159–369]	165 [145–214]
— Vegetated wetlands only	159 [119–203]	not separable
— Inland freshwaters	112 [49–202]	not separable
— Double-counting correction	−23 [−9 to −36]	—
Total natural + indirect anthro.	311 [183–462]	206 [188–225]
Total direct anthropogenic	358 [329–387]	369 [350–391] (~65%)
Total sinks	633 [507–796]	554
2020 total: 608 [581–627] top-down. Wetland area (WAD2Mv2.0): 7.9 Mkm² annual mean (13.6 Mkm² peak season). I independently verified the 575/669/159/248 figures and the 2.75 Tg/ppb footnote directly from the paper.

Critically: GMB explicitly excludes salt marshes from "wetlands" — "It also excludes coastal vegetated ecosystems (mangroves, seagrasses, salt marshes) with salinities usually > 0.5."

Coastal salt marsh — Rosentreter et al. 2023, Nature Climate Change 13:579–587, doi:10.1038/s41558-023-01682-9 (738 sites; the estimate GMB 2025 now adopts), median (Q1–Q3):

Tg CH₄ yr⁻¹	Area (km²)
Salt marshes	0.26 (0.14–0.36)	54,550 (McOwen et al. 2017)
Mangroves	0.34 (0.21–0.50)	135,813
Seagrasses	0.17 (0.09–0.21)	322,622
All coastal vegetation	0.76 (0.47–1.41)	—
Earlier/higher estimates, all from the same measurement base but using means on strongly right-skewed distributions: Rosentreter et al. 2021 (Nat. Geosci. 14:225–230) salt marsh median 0.18 (0.02–0.89) but mean 2.00 ± 1.51; Al-Haj & Fulweiler 2020 (GCB 26:2988–3005) median salt marsh flux 224.44 µmol m⁻² d⁻¹ (range −92.6 to 94,130), mean-based global ≈1.14 Tg CH₄ yr⁻¹. The median-vs-mean choice swings this by a factor of ~16 and is the substance of a published dispute (Rosentreter & Williamson 2020, doi:10.1111/gcb.15201).

Salt marsh as a fraction of global wetland CH₄: ~0.16% (0.26 / 159), full defensible envelope 0.01%–1.7% depending on median vs mean. Note this is a ratio of two independent estimates, not a partition, since GMB excludes salt marshes. Salt marsh area is 0.69% of GMB wetland area, so salt marsh is under-represented in emissions relative to area (~4.8 vs ~20 g CH₄ m⁻² yr⁻¹) — consistent with sulfate reduction outcompeting methanogenesis, which is exactly the SMARTX mechanism.

Wetland CH₄–climate feedback, for closing the loop. The number I'd lead with is the only observationally constrained one: 24 ± 10 Tg CH₄ yr⁻¹ per 1 °C of global land surface temperature (Zhang et al. 2026, Nature Geoscience, doi:10.1038/s41561-026-01987-2 — 7-model ensemble constrained by 163 site-years of eddy covariance; wetland emissions +50–60% by the 2090s under high warming). For contrast, Ury et al. 2025 Nature Sustainability 8:1115–1118 (doi:10.1038/s41893-025-01625-6, MAGICC v7 emulator) implies ~44–81 Tg CH₄ yr⁻¹ °C⁻¹ by my arithmetic from their Table 1 — 2–3× higher, and unconstrained. Their headline: "for every degree Celsius of warming avoided... an additional 3–8% of warming avoided through wetlands alone." Zhang et al. 2017 (PNAS 114:9647) gives a wetland-CH₄ feedback parameter of 0.03 ± 0.001 W m⁻² K⁻¹ under RCP8.5, worth 0.04–0.12 °C of extra warming by 2100.

Practical notes for the prototype
The only thing you can defensibly plot as the published relationship is the model form (ln F ~ T_soil + DOY + interaction) plus R² = 0.41 — the coefficients don't exist in print. If you need a curve, the honest construction is Yvon-Durocher's E_M = 0.96 eV (Q10 ≈ 3.5) anchored to a measured SMARTX ambient flux, with the treatment multipliers shown as separate measured points.
Everything in my tables labelled "derived" is arithmetic on the CC BY 4.0 archived data; the regression slopes are mine, not published, and I'd caption them as such. The R² on those slopes is low (0.21 and 0.03) because a single ΔT term ignores season — that's a real limitation, not a fitting artifact.
I wrote nothing into /Users/Pat/Documents/GitHub/marsh-methane. Downloaded sources and the flux CSV are in the session scratchpad at /private/tmp/claude-501/-Users-Pat-Documents-GitHub-marsh-methane/01e5fe52-d677-495a-b95c-281ec95a6831/scratchpad/.
Not publicly available: SMARTX observed soil temperature time series; the 96 per-plot-year regression coefficients; Rosentreter et al. 2023 Supplementary Table 6 (per-type median flux densities); Al-Haj & Fulweiler 2020 full text; Lewis et al. 2026 full text (Wiley 403 — abstract obtained via Crossref, model list via their code repo).


# Claude in progress notes group 2
The interface is built, running at http://localhost:5173, and every parameter now has a citation. Lint, type-check, and build pass. I have not committed anything.

What the literature search changed. The premise needs one correction: GCReW has never published a temperature-response equation. Noyce and Megonigal 2021 report a correlation only, R² = 0.41, and state outright that they did not quantify the temperature dependence. The 2023 paper publishes the form of its scaling model but not the fitted coefficients, and no observed soil-temperature series is archived, so they cannot be recovered. The sensitivity in the model is therefore borrowed from a 126-site synthesis, Yvon-Durocher 2014, giving Q10 of 3.50 at the site's soil temperature. Only the baseline flux is a GCReW measurement.

What I did find is better than a fitted curve. The archived chamber data is public, so I pulled it and derived the measured response myself. My numbers reproduce the published ambient values:

Warming	C3 flux, µmol m⁻² d⁻¹	C3 ratio	C4 flux	C4 ratio
ambient	419 ± 71	1.00	716 ± 175	1.00
+1.7 °C	487 ± 74	1.16	1011 ± 216	1.41
+3.4 °C	766 ± 143	1.83	976 ± 123	1.36
+5.1 °C	1950 ± 641	4.65	1281 ± 249	1.79
Those eight points are now in the model as GCREW_TREATMENTS. Nothing plots them yet, and that is the change I would make next, because the C3 threshold is the most interesting result in the experiment and a single Q10 erases it. The sedge response is near-flat to +3.4 °C then jumps to 4.6 times ambient, because the plant pumps oxygen into the soil until production overwhelms it. The Spartina response is shallower and not even monotonic.

One independent check that the chain is calibrated. The model's wetland sensitivity comes out at 19.9 teragrams of methane per year per °C. Zhang et al. 2026 constrain that observationally at 24 ± 10 using 163 site-years of eddy covariance. That agreement was not tuned. Separately, the radiative forcing code reproduces the published AR6 value exactly: 0.5440 W m⁻² against Table 7.5's printed 0.544.

Two things to decide before you show this. First, the honest feedback is nearly invisible. At +2 °C the extra methane buys 0.055 °C over 75 years, so the chart moves well but the thermometer and bubble count barely budge. I left feedbackExaggeration at 1 and it multiplies only the return leg, so you can make the loop legible without distorting the displayed flux. Second, a salt marsh alone is about 0.16% of global wetland methane, so a marsh-only feedback is climatically negligible and would not survive review. The model applies the marsh's response to the whole wetland pool instead, which is why the marsh is the mechanism on screen rather than the driver. Both points are written up in the README.

Both agents returned, and their key coefficients independently match the FaIR reference implementation I pulled myself (etminan2016: a₃=−1.3e−6, b₃=−8.2e−6, d₃=0.043, linear in M̄/N̄; meinshausen2020: a₃=−8.9603e−5, b₃=−1.2462e−4, d₃=0.045194, in √M/√N). Here is the full report.

1. Published functional form: CH₄ flux vs temperature at SMARTX
There is no published Q₁₀, activation energy, or fitted equation for SMARTX. This is the single most important finding for your prototype. What is published:

Noyce & Megonigal (2021), Results §3.2, verbatim: "Methane emissions increased with soil temperature (R² = 0.41, p < 0.001)." Methods state fluxes were log-transformed and the relationship tested with Pearson's correlation — so it is effectively an exponential (log-linear) fit, but no slope, intercept, or Q₁₀ is reported. Treatment effects were tested with categorical linear mixed models (warming treatment as a factor, not as continuous ΔT).

Noyce et al. (2023) do publish the model form used to scale monthly measurements to annual totals, in Supplementary Fig. 1 caption: "a linear regression with log CH₄ flux as the dependent variable and day-of-year, daily soil temperature, and their interaction as predictive variables." i.e.

ln(F_CH4) = β₀ + β₁·T_soil + β₂·DOY + β₃·(T_soil × DOY)

fit separately per plot per year. The Methods explain the DOY term: "the relationship between CH₄ emissions and temperature is hysteretic, with CH₄ emissions being higher at a given temperature in the fall than in the spring." Only RMSE and R² are published (Supplementary Table 1: R² ranges 0.03–1.00, mostly 0.65–0.96 across 12 plots × 4 years). The β coefficients are not published anywhere.

Lewis et al. (2026) is not a source of a temperature function either — I checked the archived code. All 10 forecast models are statistical/ML (ETS, auto.arima, prophet, XGBoost, randomForest, svm, elasticNet, brnn, rEDM, climatology). No mechanistic Q₁₀ or Arrhenius model.

So for a functional form you must either (a) borrow the canonical literature form, or (b) fit it yourself. Both options below.

Canonical published form (recommended for the visualization)
Yvon-Durocher et al. (2014), Boltzmann–Arrhenius, their Eq. 1 — this is the form Noyce cites and the standard in the field:


ln F_i(T) = (E_M + ε_EM,i)·(1/kT_C − 1/kT) + (ln F(T_C) + ε_F,i)
where T is absolute temperature (K), k = 8.617×10⁻⁵ eV K⁻¹, T_C is the mean temperature used for centring, and ε are site-level random effects.

Note the field's own caveat: Li et al. (2025, Functional Ecology, 10.1111/1365-2435.70127), using FLUXNET-CH4, finds Eₐ is strongly seasonal — unimodal, peaking at 0.60 eV in early summer and falling to −0.02 eV in late winter — i.e. much lower than 0.96 eV when the season is resolved. A single static Eₐ is a simplification worth a comment in your code.

2. Q₁₀ / activation energy with uncertainty
Quantity	Value	Source	Type
Ecosystem-scale CH₄ emission Eₐ (published version)	0.96 eV, = 57-fold increase 0→30 °C	Yvon-Durocher et al. 2014, Nature abstract	measured, meta-analysis (1553 obs, 126 sites)
Same, accepted-manuscript version	0.98 eV, 95% CI 0.88–1.08 (61-fold)	accepted MS, DiVA FULLTEXT01	measured
Methanogen cultures (population)	1.10 eV, 95% CI 0.93–1.27 (n=118, 33 units)	same	measured
Anaerobic slurries (community)	0.93 eV, 95% CI 0.82–1.03 (n=402, 47 units)	same	measured
CH₄:CO₂ efflux ratio	0.71 eV, 95% CI 0.46–0.97 (177 obs, 38 sites)	same	measured
Respiration, for contrast	~0.65 eV	same, citing Yvon-Durocher 2012	measured
Methanogenesis Q₁₀	4.1 (no uncertainty given)	Segers 1998, quoted by Noyce & Megonigal 2021	literature synthesis
Aerobic CH₄ oxidation Q₁₀	1.9 (no uncertainty given)	same	literature synthesis
⚠️ The 0.96 vs 0.98 eV discrepancy is real: the published Nature abstract says 0.96 eV / 57-fold; the green-OA accepted manuscript says 0.98 eV / 61-fold with CI 0.88–1.08. I verified the arithmetic — 0.96 eV gives exactly 56.6-fold over 0–30 °C, 0.98 eV gives 61.6-fold — so each number is internally consistent with its own text. The 95% CI I can verify (0.88–1.08) belongs to the 0.98 eV value. I could not access the published version's CI; do not assume it is 0.86–1.06.

Eₐ → Q₁₀ conversion (mine, Q10 = exp(Eₐ·10/(k·T·(T+10))), validated against the paper's own 57-fold figure):

Eₐ (eV)	Q₁₀ @10 °C	@15 °C	@20 °C	@25 °C
0.96	3.83	3.66	3.50	3.36
0.98	3.94	3.76	3.60	3.45
0.88 (CI low)	3.42	3.28	3.16	3.04
1.08 (CI high)	4.53	4.30	4.10	3.91
0.65 (respiration)	2.48	2.41	2.34	2.27
Reverse: Q₁₀ = 4.1 at 20 °C → Eₐ = 1.081 eV (104 kJ/mol); Q₁₀ = 1.9 → 0.492 eV (47 kJ/mol). Note 1 eV = 96.485 kJ/mol (the paper rounds to 96).

3. Warming treatments and measured CH₄ flux at each
Treatments (Noyce & Megonigal 2021 §2.1): 6 transects (3 per plant community), each an active gradient of ambient, +1.7, +3.4, +5.1 °C. 2 m × 2 m plots with 20 cm buffer. Above-canopy warming by infrared heaters, soil warming to 1.5 m depth by vertical resistance cables, feedback-controlled via thermocouples (Rich et al. 2015). Warming began 1 June 2016, year-round. Plus 6 elevated-CO₂ plots (see §6). 30 plots total. Site: Kirkpatrick Marsh, GCReW, Edgewater MD, 38°53′N, 76°33′W; brackish high marsh, Chesapeake Bay sub-estuary.

Published flux values
Growing season (May–Sep), both communities pooled, 2016–2019 — Noyce & Megonigal 2021, Fig. 2:

Ambient: 624 µmol CH₄ m⁻² d⁻¹
+5.1 °C: 1413 µmol CH₄ m⁻² d⁻¹ (p_adj = 0.02)
The +1.7 and +3.4 values appear only in Fig. 2 as bars — not tabulated.
Annual, scaled (Noyce & Megonigal 2021, Table S2) — this is the only fully tabulated per-treatment dataset, mean (SE) of 3 plots, mmol CH₄ m⁻² yr⁻¹:

2017	2018	2019	3-yr mean*
C3 ambient	58.4 (6.9)	161.4 (37.0)	80.4 (11.4)	100.1
C3 +1.7	69.2 (21.8)	189.2 (23.0)	82.1 (6.5)	113.5
C3 +3.4	82.6 (12.2)	178.8 (21.5)	90.7 (13.4)	117.4
C3 +5.1	178.0 (78.2)	343.2 (140.0)	317.6 (174.5)	279.6
C4 ambient	55.0 (6.9)	425.5 (88.6)	205.1 (45.2)	228.5
C4 +1.7	61.7 (12.3)	370.9 (73.7)	417.6 (156.1)	283.4
C4 +3.4	84.8 (24.5)	471.0 (96.9)	386.8 (127.6)	314.2
C4 +5.1	157.8 (37.1)	879.3 (328.9)	469.9 (175.2)	502.3
* my arithmetic, not published.

⚠️ Caution on the paper's headline numbers. The abstract-level claim "58 mmol (ambient) to 343 mmol m⁻² yr⁻¹ (+5.1 °C) in the C3 community and from 55 to 879 in the C4" mixes years — 58 and 55 are 2017 values, 343 and 879 are 2018 values. Within-year ratios are much smaller (e.g. C4 2018: 425 → 879, a 2.1× increase, not 16×). Don't quote 55→879 as a warming response.

Elevated-CO₂ experiment (Noyce et al. 2023, Fig. 5b), summer (Jun–Aug) means, 2017–2020, C3 only:

+5.1 °C alone: +317% vs ambient (p < 0.001)
eCO₂ at ambient temperature: −27% vs ambient CO₂ (p = 0.017)
eCO₂ at +5.1 °C: −59% vs warming alone (p = 0.008)
Warming + eCO₂ was not significantly different from ambient (p = 0.171)
Absolute values are in the figure only (y-axis 0–2000 µmol m⁻² d⁻¹); not tabulated.
Values I derived from the archived measured data
The full monthly flux record is public: Lewis et al. 2026 dataset, 10.25573/serc.31581154, CC BY 4.0, file SMARTX methane fluxes (2017-2024).csv (2424 observations, 30 plots, direct download https://ndownloader.figshare.com/files/62545555). Plot→treatment mapping from Raw_data/plot_treatments.csv in abbylewis/SMARTX_CH4cast.

Growing-season (May–Sep) mean CH₄ flux, 2017–2024 — plot-level means first, then mean ± SE across 3 replicate plots:

Treatment	µmol m⁻² d⁻¹	SE	mg CH₄ m⁻² h⁻¹	nmol m⁻² s⁻¹
C3 ambient	419	71	0.280	4.85
C3 +1.7	487	74	0.325	5.63
C3 +3.4	766	143	0.512	8.86
C3 +5.1	1950	641	1.303	22.6
C4 ambient	716	175	0.478	8.28
C4 +1.7	1011	216	0.676	11.7
C4 +3.4	976	123	0.652	11.3
C4 +5.1	1281	249	0.856	14.8
C3 ambient + eCO₂	311	40	0.208	3.61
C3 +5.1 + eCO₂	1147	256	0.767	13.3
Log-linear fit of the warming gradient (my fit, ambient-CO₂ plots, growing season, n excludes 96 non-positive fluxes out of 2424):


C3:  ln(F) = 5.597 + 0.2476·ΔT    slope SE 0.0212   R² = 0.213   n = 504
C4:  ln(F) = 5.814 + 0.1238·ΔT    slope SE 0.0323   R² = 0.030   n = 476
F in µmol m⁻² d⁻¹, ΔT in °C above ambient. Implied apparent Q₁₀ = 11.9 (95% CI 7.9–18.0) for C3 and 3.45 (1.8–6.5) for C4.

⚠️ Read that carefully — a warming-treatment Q₁₀ is not a seasonal/physiological Q₁₀. Warming also changes substrate supply, sulfate depletion, and plant traits (exactly the four mechanisms Noyce & Megonigal invoke), so the treatment-gradient sensitivity is inflated relative to the 0.96 eV / Q₁₀ ≈ 3.5 physiological value. The C3 value of 11.9 is not a kinetic parameter; it is the full ecosystem response including the non-linear release at +5.1 °C. Use ~3.5 for a kinetic term and the treatment table for the ecosystem response.

I could not fit the actual published equation form. No observed soil-temperature time series for SMARTX is publicly archived — I checked all 11 SMARTX datasets on Smithsonian figshare (only elevation, water level/salinity, redox, porewater, fine roots, stem density, CH₄ flux) and the forecast repo, whose only temperature data is ECMWF seasonal forecast Temp_K, not observed soil temperature. So β₁ in the Noyce 2023 model cannot be recovered from public sources.

4. Baseline / ambient CH₄ flux
Pick according to what your visualization needs:

Basis	Value	Source
Growing season, both communities pooled	624 µmol m⁻² d⁻¹ (= 0.417 mg m⁻² h⁻¹ = 7.2 nmol m⁻² s⁻¹)	Noyce & Megonigal 2021, published
Growing season, C3 ambient	419 ± 71 µmol m⁻² d⁻¹	my derivation, 2017–2024
Growing season, C4 ambient	716 ± 175 µmol m⁻² d⁻¹	my derivation, 2017–2024
Hourly, C3 ambient	20 ± 5 µmol m⁻² h⁻¹ (0.32 mg m⁻² h⁻¹, 5.6 nmol m⁻² s⁻¹)	Mueller et al. 2020, published
Hourly, C4 ambient	65 ± 37 µmol m⁻² h⁻¹ (1.04 mg m⁻² h⁻¹, 18 nmol m⁻² s⁻¹)	Mueller et al. 2020, published
Annual, C3 ambient	58–161 mmol m⁻² yr⁻¹ = 0.94–2.59 g CH₄ m⁻² yr⁻¹	Noyce & Megonigal 2021 Table S2
Annual, C4 ambient	55–426 mmol m⁻² yr⁻¹ = 0.88–6.83 g CH₄ m⁻² yr⁻¹	same
I verified Mueller's numbers are ambient-plot only: recomputing Jun–Sep 2019 from the archived data gives C3 ambient 18.9 ± 3.6 (vs published 20 ± 5 ✓) and C4 ambient 49.0 ± 12.8 (vs published 65 ± 37 — same order, within their SE). Pooling all warming treatments instead gives 35.5 and 102.8, which does not match, confirming the ambient-only reading.

Site context: across CONUS tidal marshes, annual fluxes average 26 ± 53 g CH₄ m⁻² yr⁻¹, median 3.9 (Arias-Ortiz et al. 2024, GCB 30, e17462, 10.1111/gcb.17462; 100 chamber + 9 EC sites). SMARTX ambient (~1–7 g m⁻² yr⁻¹) sits near the low-median end — expected for a brackish, sulfate-rich site.

5. Key citations
Primary warming–methane result:

Noyce, G. L. & Megonigal, J. P. (2021). Biogeochemical and plant trait mechanisms drive enhanced methane emissions in response to whole-ecosystem warming. Biogeosciences 18, 2449–2463. 10.5194/bg-18-2449-2021 — open access, supplement has Table S2.

Warming × elevated CO₂:

Noyce, G. L., Smith, A. J., Kirwan, M. L., Rich, R. L. & Megonigal, J. P. (2023). Oxygen priming induced by elevated CO₂ reduces carbon accumulation and methane emissions in coastal wetlands. Nature Geoscience 16, 63–68. 10.1038/s41561-022-01070-6. Accepted MS free at par.nsf.gov/servlets/purl/10400556; data at 10.25573/serc.21263328.

Microbial mechanism (the 2025 "microbes can't keep up" story):

Lee, J., Yang, Y., Kang, H., Noyce, G. L. & Megonigal, J. P. (2025). Climate-induced shifts in sulfate dynamics regulate anaerobic methane oxidation in a coastal wetland. Science Advances 11(17), eads6093. 10.1126/sciadv.ads6093 — OA, PMC12017331.

Predictability / 8-year record:

Lewis, A. S. L., Holmquist, J. R., Al-Haj, A. N., Read, Z. N., Rich, R. L., Megonigal, J. P. & Noyce, G. L. (2026). Warming decreases the predictability of methane emissions in a coastal wetland. Ecosphere 17(5). 10.1002/ecs2.70647. Full text paywalled (Wiley 403); abstract via Crossref; data and code are open.

Plant-species control:

Mueller, P., Mozdzer, T. J., Langley, J. A., Aoki, L. R., Noyce, G. L. & Megonigal, J. P. (2020). Plant species determine tidal wetland methane response to sea level rise. Nature Communications 11, 5154. 10.1038/s41467-020-18763-4.

Experimental design / heating system:

Noyce, G. L., Kirwan, M. L., Rich, R. L. & Megonigal, J. P. (2019). Asynchronous nitrogen supply and demand produce nonlinear plant allocation responses to warming and elevated CO₂. PNAS 116, 21623–21628. 10.1073/pnas.1904990116.

Temperature-dependence parameters:

Yvon-Durocher, G., Allen, A. P., Bastviken, D., Conrad, R., Gudasz, C., St-Pierre, A., Thanh-Duc, N. & del Giorgio, P. A. (2014). Methane fluxes show consistent temperature dependence across microbial to ecosystem scales. Nature 507, 488–491. 10.1038/nature13164. Free accepted MS: DiVA diva2:715742.

6. Plant community and elevated CO₂ — yes, both, and they change the response substantially
Communities are separate sites, not a randomized factor. The "C3 site" is >90% Schoenoplectus americanus aboveground and is lower elevation / wetter; the "C4 site" was 76% Spartina patens + Distichlis spicata in 2016, declining to 56% by 2019 (Noyce & Megonigal 2021, Table 1), and is higher elevation / drier. So community and hydrology are confounded — worth a note in your prototype.

The temperature response differs in shape, not just magnitude:

C3 (Schoenoplectus): strongly non-linear / threshold. +1.7 and +3.4 °C produce almost no change; the response appears abruptly at +5.1 °C. Their mechanism: "the relatively high capacity of Schoenoplectus to transport O₂ held the CH₄ emissions stimulation caused by modest levels of warming (+1.7 to +3.4 °C) to rates similar to under ambient conditions... At high warming (+5.1 °C), however, Schoenoplectus community CH₄ emissions drastically increase." My fitted C3 slope (0.248 per °C, apparent Q₁₀ 11.9) is dominated by this threshold. Porewater CH₄ at 40–120 cm: 43 → 1254 µmol L⁻¹ ambient → +5.1 °C.
C4 (Spartina/Distichlis): higher baseline, more gradual response. My C4 slope is half the C3 slope (0.124 per °C, Q₁₀ 3.45) and R² is only 0.03. Warming decreased deep porewater CH₄ (155 → 40 µmol L⁻¹), i.e. the mechanism is rhizodeposition-driven, not storage.
Under ambient conditions C4 emits ~2× C3; under +1.7 to +3.4 °C the gap widens to >3×; at +5.1 °C C3 catches up.
Press coverage of the 2025 result ("in areas dominated by thick sedges, methane emissions rose nearly four times higher") matches my computed C3 ratio of 4.57× (arithmetic) / 3.6× (geometric).
Elevated CO₂ (+350 ppm above ambient) is applied to the C3 community only — I confirmed from plot_treatments.csv that all 6 eCO₂ plots (610/620/630 ambient-T, 613/623/633 at +5.1 °C) are C3. It is a 2×2 factorial within C3, not crossed with community. eCO₂ suppresses the warming response, via oxygen priming: eCO₂ increases plant-mediated O₂ flux, raises soil redox potential, lowers NOSC of the DOC pool, and stimulates sulfate-dependent anaerobic CH₄ oxidation. S-DAMO rates (Lee et al. 2025, C3 community, nmol ¹³CO₂ g⁻¹ d⁻¹): ambient 0.905, warming 0.195, eCO₂ 4.194, warming+eCO₂ 5.33. S-DAMO removes 7% (C3) and 12% (C4) of CH₄ produced.

This is opposite to the global average. Chen et al. (2025), Global Change Biology 31, 10.1111/gcb.70325, meta-analysis: eCO₂ increases paddy CH₄ by 18.57% and has no significant effect in natural wetlands; warming increases natural wetland CH₄ by 26.71%. SMARTX's eCO₂ suppression is a coastal/sulfate-specific result — flag it if the prototype generalizes.

7. Closing the feedback loop: ΔCH₄ → W m⁻² → °C
The formula AR6 actually uses (Meinshausen et al. 2020 fit, AR6 Table 7.SM.1)

SARF_CH4 = (a₃·√M + b₃·√N + d₃)·(√M − √M₀)
a₃ = −8.9603×10⁻⁵, b₃ = −1.2462×10⁻⁴, d₃ = 0.045194; M = CH₄ ppb, N = N₂O ppb. N₂O overlap is the b₃√N term (no separate subtracted term). Valid 340–3500 ppb CH₄, 200–525 ppb N₂O.

SARF ≠ ERF for CH₄. AR6 §7.SM.1.3.1 applies a −14% tropospheric adjustment: ERF_CH4 = 0.86 × SARF_CH4, using Chapter 2 baselines M₀ = 729.2 ppb (not the fit's own 731.41). Verified: M = 1866.3, N = 332.1 → SARF = 0.6325, × 0.86 = 0.5440 W m⁻², matching AR6 Table 7.5's published 0.544 exactly.

Etminan et al. 2016 (the underlying paper)

ΔF_CH4 = (a₃·M̄ + b₃·N̄ + 0.043)·(√M − √M₀)
a₃ = −1.3×10⁻⁶ W m⁻² ppb⁻¹, b₃ = −8.2×10⁻⁶ W m⁻² ppb⁻¹, M̄ = ½(M+M₀), N̄ = ½(N+N₀).

⚠️ The bracket is linear in M̄ and N̄, not √M̄ and √N̄ — the form in your brief is a common mis-transcription. Confirmed two ways: the typeset Table 1 units are ppb⁻¹ (not ppb⁻¹ᐟ²), and the linear form reproduces the paper's stated 0.61 W m⁻² for 722→1803 ppb (the √ form gives 0.668, wrong by 9%). The FaIR reference implementation I pulled independently uses a3 * 0.5*(ch4+ch4_base) + b3 * 0.5*(n2o+n2o_base) + d3 — linear, confirming it.

Etminan's headline: 1750–2011 CH₄ RF 0.48 → 0.61 W m⁻² (+25%); radiative efficiency 3.63×10⁻⁴ → 4.48×10⁻⁴ W m⁻² ppb⁻¹ (+23%); GWP-100 28 → 32. Stated uncertainty ±14%.

The older simple form (Myhre 1998 / IPCC TAR–AR5, AR5 Table 8.SM.1)

ΔF = α·(√M − √M₀) − [f(M,N₀) − f(M₀,N₀)],   α = 0.036 W m⁻² ppb⁻¹ᐟ²
f(M,N) = 0.47·ln[1 + 2.01e−5·(MN)^0.75 + 5.31e−15·M·(MN)^1.52]
AR5 footnote: for CH₄ forcing, N₀ should be present-day N₂O. Verified: 722→1803 ppb at N = 324 gives 0.4844, matching AR5's published 0.48.

Present-day values and reference concentrations (AR6 Table 7.5)
1750	2011	2019	ERF 1750→2019
CH₄	729.2 ppb	1803.3	1866.3 ppb	0.544 ± 0.109 W m⁻²
N₂O	270.1 ppb	324.4	332.1 ppb	0.208 ± 0.031
CO₂	278.3 ppm	390.5	409.9 ppm	2.156 ± 0.259
Chapter 7 ES headline: CH₄ ERF = 0.54 [0.43–0.65] W m⁻² (5–95%). Ozone 0.47 [0.24–0.71]; stratospheric H₂O from CH₄ oxidation 0.05 [0.00–0.10].

⚠️ The ~1.19 W m⁻² figure is from Chapter 6, not Chapter 7, and is an emissions-based attribution: 1.19 [0.81–1.58] W m⁻² (§6.4.2, Fig. 6.12a, from Thornhill et al. 2021). It already bundles CH₄'s lifetime feedback, ozone production, stratospheric H₂O, and aerosol/HCFC-lifetime effects. Do not add it to 0.54, or to the ozone / strat-H₂O rows — that double-counts. Use 0.54 for a concentration-driven loop and 1.19 for an emissions-attribution framing, never both.

Climate sensitivity parameter λ
λ is not an AR6-assessed quantity. AR6 assesses:

ΔF₂ₓCO₂ = 3.93 ± 0.47 W m⁻² (ERF), high confidence
ECS = 3.0 °C, likely 2.5–4.0, very likely 2.0–5.0
TCR = 1.8 °C, likely 1.4–2.2, very likely 1.2–2.4
Net feedback α = −1.16 W m⁻² °C⁻¹, likely −1.54 to −0.78 (Table 7.10)
Derived λ (arithmetic, not quoted from AR6):

Route	λ (K per W m⁻²)	Range
ECS / ΔF₂ₓ = 3.0 / 3.93	0.763	0.64–1.02
−1/α = 1/1.16	0.862	0.65–1.28
TCR / ΔF₂ₓ = 1.8 / 3.93	0.458	0.36–0.56
AR6 itself flags that the α-based value is "slightly less negative than that inferred from the overall ECS assessment" — the 0.76 vs 0.86 gap is a known, acknowledged inconsistency. For a prototype, λ_eq ≈ 0.76 and λ_transient ≈ 0.46 are the internally consistent AR6 pairings.

GWPs, radiative efficiency, Tg↔ppb, lifetime
AR6 Table 7.15 (incl. chemical adjustments and carbon accounting, 5–95%):

GWP-20	GWP-100	GWP-500	GTP-100
CH₄ fossil	82.5 ± 25.8	29.8 ± 11	10.0 ± 3.8	7.5 ± 2.9
CH₄ non-fossil	79.7 ± 25.8	27.0 ± 11	7.2 ± 3.8	4.7 ± 2.9
Three different "radiative efficiency of CH₄" appear in AR6 — not interchangeable:

3.88×10⁻⁴ W m⁻² ppb⁻¹ — pure radiative, no chemical adjustments (Table 7.SM.7)
5.7×10⁻⁴ ± 1.4×10⁻⁴ — with ozone + strat-H₂O adjustments (Table 7.15); this is what feeds the GWPs
3.74×10⁻⁴ — local dERF/dM at 1866.3 ppb from the concentration formula. For a small perturbation on today's atmosphere this is the right direct number; scale by 5.7/3.88 ≈ 1.47 to include chemistry. (The 1750–2019 average is 0.544/1137.1 = 4.78×10⁻⁴ — do not use this as a marginal sensitivity.)
Tg ↔ ppb: 2.75 Tg CH₄ per ppb (= 0.3636 ppb per Tg), from Prather, Holmes & Hsu (2012), GRL 39, L09803, 10.1029/2012GL051440. Cited verbatim in AR6 Ch. 6 Table 6.2 caption and in Saunois et al. 2025 Table 3 footnote f — I independently confirmed the latter in the PDF text. 2.78 is not an AR6 number and no authoritative source was found for it; use 2.75. (The naïve whole-atmosphere mass value is ~2.85; 2.75 is lower because surface-network mole fractions exceed the true global mean.)

Lifetimes (AR6 Ch. 6, Table 6.2) — your brief has these slightly crossed:

AR6	AR5
Total atmospheric lifetime	9.1 ± 0.9 yr	9.25 ± 0.6
OH feedback factor f	1.30 ± 0.07	1.34 ± 0.06
Perturbation lifetime	11.8 ± 1.8 yr	12.4 ± 1.4
The 11.8 ± 1.8 yr in Table 7.15 is the perturbation lifetime (the correct decay constant for an emissions-driven box model), not the total atmospheric lifetime. 12.4 yr is the superseded AR5 value, not AR6.

8. Scaling up: global wetland and salt marsh totals
Global Methane Budget (Saunois et al. 2025, ESSD 17, 1873–1958, 10.5194/essd-17-1873-2025)
All Tg CH₄ yr⁻¹, 2010–2019; brackets are [min–max] of the model ensemble, not confidence intervals (their Table 3 caption, outliers discarded). I verified the headline numbers directly in the PDF.

Bottom-up	Top-down
Total sources	669 [512–849]	575 [553–586]
Wetlands + inland freshwaters	248 [159–369]	165 [145–214]
— vegetated wetlands only	159 [119–203]	not separable
— inland freshwaters	112 [49–202]	not separable
— double-counting correction	−23 [−9 to −36]	—
Other natural	63 [24–93]	43 [40–46]
Total natural + indirect anthro	311 [183–462]	206 [188–225]
Total direct anthropogenic	358 [329–387]	369 [350–391] (≈65%)
Total sinks	633 [507–796]	554 [550–567]
Year 2020: 608 [581–627] top-down (12% above the 2000s mean). Wetland area used: WAD2Mv2.0, 7.9 Mkm² annual mean (peak 13.6 Mkm²). Wetlands ≈ 25% of total bottom-up sources and remain the largest single uncertainty in the budget.

Critical definitional point: the GMB explicitly excludes coastal vegetated ecosystems from "wetlands" — verbatim: "It also excludes coastal vegetated ecosystems (mangroves, seagrasses, salt marshes) with salinities usually > 0.5." So salt marsh is not a subset of the 159 Tg; any ratio you compute is between two independent estimates, not a partition.

Prior version for reference: Saunois et al. 2020, ESSD 12, 1561–1623, 2008–2017: total 737 [594–881] BU / 576 [550–594] TD; wetlands 149 [102–182] BU / 181 [159–200] TD.

Coastal salt marsh CH₄
Best current estimate — Rosentreter et al. 2023, Nature Climate Change 13, 579–587, 10.1038/s41558-023-01682-9 (738 sites; this is what GMB 2025 itself now adopts):

Tg CH₄ yr⁻¹, median (Q1–Q3)	Area (km²)
Salt marshes	0.26 (0.14–0.36)	54,550
Mangroves	0.34 (0.21–0.50)	135,813
Seagrasses	0.17 (0.09–0.21)	322,622
All coastal vegetation	0.76 (0.47–1.41)	—
Implied salt marsh areal flux (derived): 4.8 g CH₄ m⁻² yr⁻¹ = 13.1 mg m⁻² d⁻¹. Highest regional flux density reported: East Asian salt marshes at 44 mg CH₄ m⁻² d⁻¹.

Alternative estimates, which differ by >10× depending on median vs mean — this is the live methodological dispute in the literature:

Source	Salt marsh (Tg CH₄ yr⁻¹)	Basis
Rosentreter et al. 2023	0.26 (0.14–0.36)	median
Rosentreter et al. 2021, Nat. Geosci. 14, 225	0.18 (0.02–0.89)	median
Rosentreter et al. 2021	2.00 ± 1.51	mean
Al-Haj & Fulweiler 2020, GCB 26, 2988	~1.14	mean-based, reproduced from their public data+code
Saunois et al. 2020 (superseded)	4–5 (incl. estuaries+mangroves)	small n≈80
Al-Haj & Fulweiler's published salt marsh flux: median 224.44 µmol m⁻² d⁻¹ (range −92.60 to 94,129.68), mean 3,534.90 µmol m⁻² d⁻¹ = 56.7 mg m⁻² d⁻¹. The median/mean gap (factor ~16) is the whole point of the Rosentreter & Williamson (2020) comment, 10.1111/gcb.15201, with reply at 10.1111/gcb.15245 (both paywalled, not retrieved). Global salt marsh area: 55,000 km² (McOwen et al. 2017, 10.3897/BDJ.5.e11764); Rosentreter 2023 notes published estimates span 55,000–90,800 km².

Salt marsh as a fraction of global wetland CH₄
~0.16% using the best-supported pairing (Rosentreter 2023 median 0.26 Tg ÷ GMB 2025 bottom-up wetlands 159 Tg). Defensible full envelope 0.01%–1.7% depending on median vs mean. Against the 248 Tg combined wetland+freshwater figure it is 0.10%.

For scale: salt marsh area (54,550 km²) is 0.69% of GMB's annual-mean wetland area (7.9 Mkm²), so salt marsh is under-represented in emissions relative to area — areal flux 4.8 vs ~20.1 g CH₄ m⁻² yr⁻¹ for wetlands generally, a factor of ~4, consistent with sulfate reduction outcompeting methanogenesis. This is the honest headline for your prototype: a single salt marsh site is a mechanistic window, not a large term in the global budget.

Regional check: US East Coast tidal marshes = 0.019–0.038 Tg CH₄ yr⁻¹ (Cai, Yang & Raymond, arXiv:2512.14076; modeled, remote sensing + ocean model).

Wetland CH₄–climate feedback (the per-degree number you need)
Lead with this one — it is the only observationally constrained sensitivity:

Zhang et al. (2026). Emergent constraints on future methane emissions from global wetlands. Nature Geoscience, 10.1038/s41561-026-01987-2. Verbatim: "for every 1 °C increase in global land surface temperature, there is a 24 ± 10 Tg CH₄ yr⁻¹ increase." Seven-model ensemble constrained by 163 site-years of eddy-covariance flux data. Wetland emissions rise 50–60% by the 2090s under high warming. Caveat stated by the authors: constraint dominated by mid/high-latitude sites, limited tropical coverage.

Others, all modeled (no observational constraint on the sensitivity itself):

Ury, Zhang & Buma 2025, Nature Sustainability 8, 1115–1118, 10.1038/s41893-025-01625-6: wetland CH₄ grows +23–277 Tg CH₄ yr⁻¹ by 2100; SSP2-4.5 2100 warming +2.6 °C → +2.8 °C with the wetland feedback; "for every degree Celsius of warming avoided... an additional 3–8% of warming avoided through wetlands alone." Their implied per-degree slope (my arithmetic from their Table 1) is ~44–81 Tg CH₄ yr⁻¹ °C⁻¹ — 2–3× the observationally constrained 24 ± 10, worth flagging. MAGICC v7 emulator.
Zhang et al. 2017, PNAS 114, 9647: 172 ± 12 → 338 ± 28 Tg CH₄ yr⁻¹ by 2100 under RCP8.5; wetland-CH₄ feedback parameter λ ≈ 0.03 ± 0.001 W m⁻² K⁻¹; RF 0.04 → 0.19 W m⁻²; +0.04 to +0.12 °C additional GMST.
Kleinen et al. 2021, ERL 16, 094006: natural CH₄ +22% to +149% by 2100 (269–548 Tg CH₄ yr⁻¹ across SSPs); "natural emissions rise roughly proportionally to temperature change."
Koffi et al. 2020, Sci. Adv. 6, eaay4444: inversion-constrained; baseline 175 Tg CH₄ yr⁻¹ over 4.69 Mkm²; +40–60% by 2100 (current area) or +50–80% with expansion.
Zhang et al. 2023, Nat. Clim. Change 13, 430: observed trend +1.3–1.4 Tg CH₄ yr⁻¹ per year, 2000–2021; 2007–2021 emissions +5–6% (8–10 Tg CH₄ yr⁻¹) vs 2000–2006.
Measured vs modeled, and what is genuinely unavailable
Measured (chamber flux): all SMARTX treatment values in §3–4; Mueller's hourly baselines; the Arias-Ortiz CONUS synthesis; all coastal salt marsh totals (data-driven upscaling of chamber/gradient measurements × area maps — not atmospherically constrained).
Measured meta-analysis: the Yvon-Durocher activation energies.
Modeled, bottom-up process: GMB wetland 159; Zhang 2017/2023; Kleinen 2021.
Modeled, top-down inversion: GMB total 575; wetland+freshwater 165 (cannot separate wetlands from freshwaters, let alone resolve salt marsh).
Assessed / semi-empirical: all AR6 forcing, ECS, TCR, GWP values. λ is derived, not assessed.
My own arithmetic, labelled as such: the 8-year treatment table, the log-linear slopes and apparent Q₁₀s, all unit conversions, Eₐ→Q₁₀ conversions, the salt-marsh-fraction ratios, and the Ury per-degree slope.

Not publicly available — state this rather than filling it in:

Any fitted temperature-response coefficient for SMARTX. Only the model form (Noyce 2023) and R² values exist. No observed soil-temperature time series is archived for any SMARTX dataset, so β₁ cannot be recovered from public sources.
Per-treatment absolute flux values for +1.7 and +3.4 °C in Noyce & Megonigal 2021 Fig. 2 and Noyce 2023 Fig. 5 (figures only, no table).
Lewis et al. 2026 full text (Wiley 403) — abstract and data/code only.
Rosentreter 2023 Supplementary Table 6 and Rosentreter 2021 Extended Data Table 1 (per-type median areal fluxes).
Al-Haj & Fulweiler 2020 full text; the per-ecosystem split above is reproduced from their figshare data + GitHub code, which validates against their published 0.331–0.389 Tmol total.
AR6's GSAT contribution attributed to CH₄ emissions (graphical only, Fig. 6.12b).
Two transcription traps to avoid, both verified numerically: the Etminan bracket is linear in M̄/N̄ (not √M̄/√N̄), and the 1.19 W m⁻² is an emissions-based attribution that must not be added to the 0.54 concentration-based ERF.

Everything I downloaded is in the session scratchpad; nothing was written into the repo. The one file worth pulling into the project is the measured 8-year flux record: https://ndownloader.figshare.com/files/62545555 (CC BY 4.0), plus plot_treatments.csv from the GitHub repo for the plot→treatment mapping.

# Claude in progress notes group 3
That last notification was a repeat from the research agent, not new information. Everything in it matched what I had already implemented and independently verified against the archived data.

Final state. The prototype is at /Users/Pat/Documents/GitHub/marsh-methane, running on the dev server at http://localhost:5173. Lint, type-check, and build all pass. Nothing is committed.

The one change I made after my last message was a comment, not behavior. The model baseline uses Mueller et al. 2020's published 0.32 mg m⁻² h⁻¹ from 2019, while the measured treatment table carries 0.280 for the same plots averaged over 2017 to 2024. Those differ because interannual variation at this site is larger than the warming effect. I documented why rather than quietly reconciling them, and noted which line to edit if you want them identical.

Two independent checks that the science is right, both of which I ran myself rather than taking on trust:

The radiative forcing code reproduces AR6 Table 7.5 exactly, 0.5440 against a published 0.544.
The model's wetland sensitivity of 19.9 teragrams of methane per year per °C sits inside Zhang et al. 2026's observationally constrained 24 ± 10. That was not tuned.
I also re-derived the eight measured treatment points from the archived chamber data, 2424 observations across 30 plots, and reproduced the published ambient values. Those are now in the repo as real GCReW data.

What I would not ship without your call. The honest feedback is nearly invisible, 0.055 °C at a +2 °C start, and a salt marsh alone is roughly 0.16% of global wetland methane. Both are judgment calls about framing rather than code, both are written up in the README, and the amplification knob is there at 1 so nothing is exaggerated until you decide to exaggerate it.

# Claude in progress notes group 4
The README is written, at /Users/Pat/Documents/GitHub/marsh-methane/README.md. Lint, type-check, and build pass, and the running app matches the numbers in the document.

I found and fixed a real error while writing it. The Q10 constant was 3.459, not 3.50. A Q10 is not constant under an Arrhenius law, and 3.50 is the value at 20 °C while the model's baseline soil temperature is 21.5 °C. Writing the conversion out forced the check. My formula reproduces the source paper's own stated 57-fold increase from 0 to 30 °C, giving 56.6, which is how I know the conversion itself is right. The effect on outputs is small but the inconsistency would have been visible to a reviewer.

What the document contains, in ten sections:

The reasoning chain written as six steps, each with its equation and the source for every term, including why the perturbation lifetime of 11.8 years is correct rather than the 9.1-year total lifetime, and why the non-wetland emission term is derived rather than specified.
A constants table marking each value as measured, derived, assessed, assumption, or placeholder. Only one placeholder remains.
The measured GCReW data with its method, and a direct comparison against the modelled curve. That comparison is the most useful thing in the write-up: the smooth exponential tracks the Spartina community but under-predicts the Schoenoplectus threshold at +5.1 °C by a factor of about 2.5. The measured ratio is 4.65 and the model gives 1.88.
Four validation checks with their results, including the forcing code reproducing AR6's published 0.544 W m⁻² and the wetland sensitivity landing inside Zhang et al. 2026's observational constraint.
Honest weaknesses as a plain list, covering the tiny feedback, the single Q10 applied to all wetlands, the omitted ozone and stratospheric water vapour terms, and the fact that none of this reasoning currently reaches the user on screen.
Two transcription traps recorded numerically, so nobody extending the model reintroduces them.
Full references grouped by role, each annotated with what it supplies, plus a short list of what is genuinely not publicly available so nobody repeats the search.
One thing worth flagging: the document says the C3 apparent per-10 °C factor of 11.9 should not be called a Q10, because a sustained warming treatment also depletes sulfate and shifts plant traits. If that number gets quoted in a talk, it will be challenged.