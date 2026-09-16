#!/usr/bin/env python3
"""Build ssp-ch4-feedback.json (the browser data bundle) and the validation
fixtures that ch4feedback.js is checked against.

    python3 build_bundle.py
"""
import json
import numpy as np
import ch4feedback as m

CORE = ["ssp126", "ssp245", "ssp370", "ssp585"]
YEAR_MIN, YEAR_MAX = 1750, 2300


def r(a, nd):
    """Round to nd decimals and return a plain list (keeps the JSON small)."""
    return [round(float(x), nd) for x in a]


def main():
    scen = {k: m.build_scenario(k) for k in m.SCENARIO_REGISTRY}

    params, diag = m.calibrate({k: scen[k] for k in CORE},
                               fit=("tau_base", "e_nat"),
                               start_year=1850, end_year=2100)

    # ---- per-scenario skill against the prescribed CMIP6 pathway ----------
    skill = {}
    for k, s in scen.items():
        run = m.run(s, params, 1850, 2100)
        mask = (s["year"] >= 1850) & (s["year"] <= 2100)
        d = run["ch4"] - s["ch4_cmip6"][mask]
        i = list(s["year"]).index(2100)
        base = run["temperature"][(run["year"] >= 1850) & (run["year"] <= 1900)].mean()
        skill[k] = {
            "ch4_rmse_ppb": round(float(np.sqrt(np.mean(d ** 2))), 1),
            "ch4_2100_error_pct": round(float(100 * d[-1] / s["ch4_cmip6"][i]), 1),
            "warming_2081_2100_K": round(float(
                run["temperature"][run["year"] >= 2081].mean() - base), 2),
            "calibration_scenario": k in CORE,
        }

    out = {
        "meta": {
            "title": "Coupled CH4-temperature feedback: SSP scenario inputs",
            "generated_by": "build_bundle.py (see README.md)",
            "description": (
                "Per-scenario annual inputs for a browser-side coupled methane "
                "box model and two-layer energy balance. Everything that does "
                "NOT depend on CH4 or temperature is pre-summed into f_other, "
                "so the live model only has to integrate the coupled part."
            ),
            "sources": {
                "emissions_and_concentrations": (
                    "Hector scenario input tables (JGCRI), repackaging RCMIP "
                    "v5.1.0 harmonised SSP emissions (Nicholls et al. 2020) and "
                    "the CMIP6 prescribed GHG concentrations of Meinshausen et "
                    "al. (2020)."),
                "forcing_and_chemistry_coefficients": (
                    "FaIR 2.1 default species configuration (AR6-consistent): "
                    "radiative efficiencies, tropospheric adjustments, ozone and "
                    "aerosol coefficients, CH4 lifetime sensitivities."),
                "ghg_forcing_formulas": "Meinshausen et al. (2020)",
                "energy_balance": "two-layer, Geoffroy et al. (2013) structure",
            },
            "units": {
                "year": "calendar year",
                "ch4_emissions": "Tg CH4 yr-1, ANTHROPOGENIC ONLY",
                "n2o": "ppb (needed for the CH4-N2O band overlap)",
                "f_other": "W m-2, all forcing independent of CH4 and temperature",
                "alpha_chem_ext": ("dimensionless CH4-lifetime scaling from N2O, "
                                   "EESC, NOx and VOC"),
                "ch4_cmip6": "ppb, prescribed CMIP6 pathway (benchmark, not input)",
            },
            "validation": {
                "erf_2019_vs_ar6": (
                    "every component within 0.03 W m-2; total 2.68 vs AR6 2.72 "
                    "(the gap is contrails, which are omitted)"),
                "warming_2011_2020_K": 1.00,
                "warming_2011_2020_observed_K": 1.09,
                "note": ("SSP4-3.4 and SSP4-6.0 track the prescribed CH4 pathway "
                         "poorly (+21% and +17% at 2100). Prefer the four "
                         "calibration scenarios."),
            },
        },
        "constants": {
            "ppb_to_tg": round(m.PPB_TO_TG, 6),
            "ch4_baseline_ppb": m.BASE["ch4"],
            "n2o_baseline_ppb": m.BASE["n2o"],
            "meinshausen_ch4": {"a3": m.MEIN["a3"], "b3": m.MEIN["b3"],
                                "d3": m.MEIN["d3"]},
            "ch4_tropospheric_adjustment": m.TROP_ADJ["ch4"],
            "s_ch4_per_ppb": m.S_CH4_PER_PPB,
            "ozone_re_ch4": m.OZONE_RE_CH4,
            "h2o_strat_ch4": m.H2O_STRAT_CH4,
            "erfari_re_ch4": m.ERFARI_RE_CH4,
        },
        "defaults": {
            k: (round(v, 6) if isinstance(v, float) else v)
            for k, v in vars(params).items()
        },
        "calibration": {
            "fitted": {k: round(v, 4) for k, v in diag["fitted"].items()},
            "scenarios": diag["scenarios"],
            "window": list(diag["window"]),
            "rmse_ppb": round(diag["rmse_ppb"], 1),
            "note": ("tau_base and e_nat are EFFECTIVE parameters fitted to "
                     "emulate MAGICC7, not measurements. Fixing e_nat to the "
                     "bottom-up ~205 Tg yr-1 gives a more realistic 9.1 yr "
                     "present-day lifetime but more than doubles the CH4 error."),
            "skill_by_scenario": skill,
        },
        "scenarios": {},
    }

    # Build the ROUNDED arrays that actually ship, then use those same arrays
    # for the validation fixtures. Generating fixtures from full-precision
    # arrays makes the JS look wrong at ~3e-5 when it is only reading the
    # rounded JSON - the test would be measuring my own rounding.
    rounded = {}
    for k, s in scen.items():
        mask = (s["year"] >= YEAR_MIN) & (s["year"] <= YEAR_MAX)
        out["scenarios"][k] = {
            "label": s["label"],
            "year_start": int(s["year"][mask][0]),
            "ch4_emissions": r(s["ch4_emissions"][mask], 4),
            "n2o": r(s["n2o"][mask], 4),
            "f_other": r(s["f_other"][mask], 6),
            "alpha_chem_ext": r(s["alpha_chem_ext"][mask], 8),
            "ch4_cmip6": r(s["ch4_cmip6"][mask], 2),
        }
        b = out["scenarios"][k]
        rounded[k] = {
            "slug": k, "label": s["label"],
            "year": np.arange(b["year_start"],
                              b["year_start"] + len(b["ch4_emissions"])),
            "ch4_emissions": np.array(b["ch4_emissions"]),
            "n2o": np.array(b["n2o"]),
            "f_other": np.array(b["f_other"]),
            "alpha_chem_ext": np.array(b["alpha_chem_ext"]),
            "ch4_cmip6": np.array(b["ch4_cmip6"]),
        }

    with open("ssp-ch4-feedback.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote ssp-ch4-feedback.json  "
          f"({len(json.dumps(out, separators=(',', ':'))) / 1024:.0f} KB)")

    # ---- validation fixtures: a parameter sweep for the JS to reproduce ----
    cases = []
    for slug in ["ssp126", "ssp245", "ssp585"]:
        for gw in [0.0, 20.0, 40.0]:
            for ecs in [2.0, 3.0, 4.5]:
                for st in [0.0, m.S_TEMPERATURE]:
                    p = params.replace(gamma_wetland=gw, ecs=ecs, s_temperature=st)
                    run = m.run(rounded[slug], p, 1850, 2100)
                    cases.append({
                        "scenario": slug,
                        "params": {"gamma_wetland": gw, "ecs": ecs,
                                   "s_temperature": st},
                        "start_year": 1850, "end_year": 2100,
                        "expect": {
                            "ch4_2100": float(run["ch4"][-1]),
                            "temperature_2100": float(run["temperature"][-1]),
                            "forcing_2100": float(run["forcing"][-1]),
                            "tau_2100": float(run["tau"][-1]),
                            "ch4_2050": float(run["ch4"][list(run["year"]).index(2050)]),
                            "temperature_2050": float(
                                run["temperature"][list(run["year"]).index(2050)]),
                        },
                    })
    json.dump({"defaults": out["defaults"], "cases": cases},
              open("validation_fixtures.json", "w"), indent=1)
    print(f"wrote validation_fixtures.json ({len(cases)} cases)")


if __name__ == "__main__":
    main()
