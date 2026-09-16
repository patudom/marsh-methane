"""
Coupled methane-temperature feedback model: the Python reference implementation.

    temperature  ->  natural CH4 emissions  ->  CH4 burden  ->  forcing  ->  temperature

This is the authority that ch4feedback.js is validated against. Both use the same
fixed-step RK4 integrator so they should agree to round-off.

Physics, and where each piece comes from
----------------------------------------
CH4 burden        dB/dt = E_anth(t) + E_nat + gamma_wetland * T - B / tau
CH4 lifetime      tau = tau_base * alpha_chem_ext(t) * (1 + dCH4*s_ch4) * (1 + T*s_T)
                  Multiplicative sensitivities and their values are FaIR 2.1's
                  default species config (AR6-consistent): CH4 +2.54e-4 /ppb,
                  N2O -7.23e-4 /ppb, EESC -5e-6 /ppt, NOx -2.565e-3 /(Mt NO2/yr),
                  VOC +1.619e-3 /(Mt/yr), temperature -0.0408 /K.
Temperature       two-layer energy balance (Geoffroy et al. 2013; Held et al. 2010)
                  C  dT/dt  = F - lambda*T - epsilon*kappa*(T - T_d)
                  C_d dT_d/dt = kappa*(T - T_d)
Forcing           F = f_other(t) + F_CH4(CH4,N2O) + CH4's ozone and stratospheric
                  water terms + CH4's aerosol-radiation term + ozone's own
                  temperature feedback.

The two legs of the loop
------------------------
POSITIVE  gamma_wetland: warming raises wetland (and permafrost) CH4 emissions.
          AR6 assesses the combined non-CO2 biogeochemical feedback at
          0.02-0.09 W m-2 degC-1 with LOW confidence, which is about
          7-30 Tg CH4 yr-1 K-1 here. Default 20; there is no defensible
          single value, which is why it belongs on a slider.
NEGATIVE  s_T = -0.0408 /K: warming means more water vapour, more OH, and a
          shorter CH4 lifetime. Plus the ozone forcing temperature feedback,
          -0.037 W m-2 K-1. These damp the loop. It does not run away.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, replace

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Atmospheric constants
# --------------------------------------------------------------------------- #

MASS_ATMOSPHERE = 5.1352e18       # kg, dry air
MW_AIR = 28.97                    # g/mol
MW_CH4 = 16.043                   # g/mol

#: Tg(CH4) per ppb. NOTE this is the exact mole-fraction-to-mass conversion
#: (2.844), which is what FaIR's calibrated sensitivities assume. The IPCC
#: assessment tables use 2.75, which additionally corrects for surface networks
#: over-sampling the CH4-rich lower troposphere. Using 2.844 here keeps us
#: consistent with the coefficients; it shifts the FITTED tau_base and e_nat by
#: about 3% and changes nothing else.
PPB_TO_TG = MASS_ATMOSPHERE * (MW_CH4 / MW_AIR) * 1e-9 / 1e9

#: FaIR 2.1 default species-config baselines (the reference state all the
#: radiative efficiencies and chemical sensitivities are defined against).
BASE = {"co2": 278.3, "ch4": 729.2, "n2o": 270.1, "eesc": 344.362759,
        "so2": 2.440048, "bc": 2.097771, "oc": 15.447668, "nh3": 6.927690,
        "nox": 12.735212, "voc": 60.021826, "co": 348.527359}

#: Meinshausen et al. (2020) GHG forcing coefficients.
MEIN = dict(a1=-2.4785e-07, b1=7.5906e-04, c1=-2.1492e-03, d1=5.2488,
            a2=-3.4197e-04, b2=2.5455e-04, c2=-2.4357e-04, d2=0.12173,
            a3=-8.9603e-05, b3=-1.2462e-04, d3=0.045194)

#: Tropospheric rapid adjustments, ERF/RF - 1 (FaIR default config).
TROP_ADJ = {"co2": 0.05, "ch4": -0.14, "n2o": 0.07}

#: CH4 lifetime sensitivities, FaIR 2.1 default config.
S_CH4_PER_PPB = 2.54e-4
S_N2O_PER_PPB = -7.23e-4
S_EESC_PER_PPT = -5.0e-6
S_NOX = -2.565e-3
S_VOC = 1.619e-3
S_TEMPERATURE = -0.0408

#: Per-ppb CH4 terms beyond its own greenhouse forcing (FaIR default config).
OZONE_RE_CH4 = 1.75e-4        # W m-2 ppb-1, tropospheric ozone from CH4
H2O_STRAT_CH4 = 4.4e-5        # W m-2 ppb-1, stratospheric water vapour from CH4
ERFARI_RE_CH4 = -2.0e-6       # W m-2 ppb-1, aerosol-radiation from CH4
OZONE_TEMP_FEEDBACK = -0.037  # W m-2 K-1

#: Ozone radiative efficiencies of the other precursors.
OZONE_RE = {"n2o": 7.10e-4, "eesc": -1.25e-4, "nox": 1.80e-3,
            "voc": 3.29e-4, "co": 1.55e-4}

#: Aerosol-radiation radiative efficiencies (W m-2 per emission unit / per ppb).
ERFARI_RE = {"so2": -2.860e-3, "bc": 2.100e-2, "oc": -3.960e-3,
             "nh3": -5.650e-4, "nox": -6.70e-5, "voc": -1.60e-5,
             "n2o": -3.60e-5, "eesc": -7.0e-6}

#: Aerosol-cloud interaction (FaIR "logsum" form).
ACI_SCALE = -1.030572
ACI_SHAPE = {"so2": 0.0169, "bc": 1.04e-15, "oc": 0.0309}

#: Black carbon on snow and ice.
LAPSI_RE_BC = 1.158593e-02

#: Unit conversions from the Hector/RCMIP scenario tables to FaIR conventions.
SO2_GG_S_TO_MT_SO2 = (64.069 / 32.06) / 1000.0   # Gg S -> Mt SO2
NOX_TG_N_TO_MT_NO2 = 46.006 / 14.007             # Tg N  -> Mt NO2

#: EESC: (species, cl atoms, br atoms, fractional release), FaIR default config.
EESC_SPECIES = [
    ("CFC11_constrain", 3, 0, 0.47), ("CFC12_constrain", 2, 0, 0.23),
    ("CFC113_constrain", 3, 0, 0.29), ("CFC114_constrain", 2, 0, 0.12),
    ("CFC115_constrain", 1, 0, 0.04), ("HCFC22_constrain", 1, 0, 0.13),
    ("HCFC141b_constrain", 2, 0, 0.34), ("HCFC142b_constrain", 1, 0, 0.17),
    ("CCl4_constrain", 4, 0, 0.56), ("CH3Cl_constrain", 1, 0, 0.44),
    ("CH3CCl3_constrain", 3, 0, 0.67), ("CH3Br_constrain", 0, 1, 0.60),
    ("halon1211_constrain", 1, 1, 0.62), ("halon1301_constrain", 0, 1, 0.28),
    ("halon2402_constrain", 0, 2, 0.65),
]
BR_CL_RATIO = 45.0
CFC11_FR = 0.47

#: Minor GHGs: (scenario column, radiative efficiency W m-2 ppb-1, trop. adj.).
MINOR_GHG = [
    ("CFC11_constrain", 0.25941, 0.13), ("CFC12_constrain", 0.31998, 0.12),
    ("CFC113_constrain", 0.30142, 0.0), ("CFC114_constrain", 0.31433, 0.0),
    ("CFC115_constrain", 0.24625, 0.0), ("HCFC22_constrain", 0.21385, 0.0),
    ("HCFC141b_constrain", 0.16065, 0.0), ("HCFC142b_constrain", 0.19329, 0.0),
    ("CCl4_constrain", 0.16616, 0.0), ("CH3Cl_constrain", 0.00466, 0.0),
    ("CH3CCl3_constrain", 0.06454, 0.0), ("CH3Br_constrain", 0.00432, 0.0),
    ("halon1211_constrain", 0.30014, 0.0), ("halon1301_constrain", 0.29943, 0.0),
    ("halon2402_constrain", 0.31169, 0.0), ("CF4_constrain", 0.09859, 0.0),
    ("C2F6_constrain", 0.26105, 0.0), ("SF6_constrain", 0.56657, 0.0),
    ("HFC23_constrain", 0.19111, 0.0), ("HFC32_constrain", 0.11144, 0.0),
    ("HFC125_constrain", 0.23378, 0.0), ("HFC134a_constrain", 0.16714, 0.0),
    ("HFC143a_constrain", 0.16800, 0.0), ("HFC227ea_constrain", 0.27325, 0.0),
    ("HFC245fa_constrain", 0.24498, 0.0), ("HFC4310_constrain", 0.35731, 0.0),
]
#: Baseline concentrations for the minor GHGs that are non-zero in 1750 (ppt).
MINOR_BASE = {"CCl4_constrain": 0.025, "CH3Cl_constrain": 457.0,
              "CH3Br_constrain": 5.3, "halon1211_constrain": 0.00445,
              "CF4_constrain": 34.05}


# --------------------------------------------------------------------------- #
# Forcing pieces
# --------------------------------------------------------------------------- #

def erf_co2(co2, n2o, co2_base=BASE["co2"], n2o_base=BASE["n2o"]):
    """CO2 ERF [W m-2], Meinshausen et al. (2020), with the N2O overlap."""
    m = MEIN
    co2 = np.asarray(co2, float)
    ca_max = co2_base - m["b1"] / (2 * m["a1"])
    d = co2 - co2_base
    alpha_p = np.where(
        co2 <= co2_base, m["d1"],
        np.where(co2 <= ca_max,
                 m["d1"] + m["a1"] * d ** 2 + m["b1"] * d,
                 m["d1"] - m["b1"] ** 2 / (4 * m["a1"])),
    )
    alpha_n2o = m["c1"] * np.sqrt(np.asarray(n2o, float))
    return (alpha_p + alpha_n2o) * np.log(co2 / co2_base) * (1 + TROP_ADJ["co2"])


def erf_ch4(ch4, n2o, ch4_base=BASE["ch4"]):
    """CH4 ERF [W m-2], Meinshausen et al. (2020), with the N2O overlap."""
    m = MEIN
    ch4, n2o = np.asarray(ch4, float), np.asarray(n2o, float)
    return ((m["a3"] * np.sqrt(ch4) + m["b3"] * np.sqrt(n2o) + m["d3"])
            * (np.sqrt(ch4) - np.sqrt(ch4_base))) * (1 + TROP_ADJ["ch4"])


def erf_n2o(co2, ch4, n2o, n2o_base=BASE["n2o"]):
    """N2O ERF [W m-2], Meinshausen et al. (2020), with CO2 and CH4 overlaps."""
    m = MEIN
    co2, ch4, n2o = (np.asarray(x, float) for x in (co2, ch4, n2o))
    return ((m["a2"] * np.sqrt(co2) + m["b2"] * np.sqrt(n2o)
             + m["c2"] * np.sqrt(ch4) + m["d2"])
            * (np.sqrt(n2o) - np.sqrt(n2o_base))) * (1 + TROP_ADJ["n2o"])


def erf_ch4_extras(ch4, ch4_base=BASE["ch4"]):
    """CH4's non-greenhouse terms: ozone, stratospheric H2O, aerosol-radiation."""
    d = np.asarray(ch4, float) - ch4_base
    return d * (OZONE_RE_CH4 + H2O_STRAT_CH4 + ERFARI_RE_CH4)


def compute_eesc(df):
    """Equivalent effective stratospheric chlorine [ppt CFC-11-eq]."""
    total = np.zeros(len(df))
    for col, cl, br, fr in EESC_SPECIES:
        if col not in df:
            continue
        c = df[col].to_numpy(float)
        total += (cl * c * fr / CFC11_FR + BR_CL_RATIO * br * c * fr / CFC11_FR) * CFC11_FR
    return total


def scenario_forcing_terms(df):
    """Split a scenario's forcing into what depends on CH4/T and what doesn't.

    Returns a dict with ``f_other`` (W m-2; every component untouched by CH4 or
    temperature) and ``alpha_chem_ext`` (the CH4-lifetime scaling from N2O,
    EESC, NOx and VOC), plus the individual 2019-checkable components.
    """
    co2 = df["CO2_constrain"].to_numpy(float)
    ch4 = df["CH4_constrain"].to_numpy(float)
    n2o = df["N2O_constrain"].to_numpy(float)
    eesc = compute_eesc(df)

    so2 = df["SO2_emissions"].to_numpy(float) * SO2_GG_S_TO_MT_SO2
    nox = df["NOX_emissions"].to_numpy(float) * NOX_TG_N_TO_MT_NO2
    bc = df["BC_emissions"].to_numpy(float)
    oc = df["OC_emissions"].to_numpy(float)
    nh3 = df["NH3_emissions"].to_numpy(float)
    voc = df["NMVOC_emissions"].to_numpy(float)
    co = df["CO_emissions"].to_numpy(float)

    # --- greenhouse gases other than CH4 -----------------------------------
    f_co2 = erf_co2(co2, n2o)
    f_n2o = erf_n2o(co2, ch4, n2o)      # uses prescribed CH4: see note below
    f_minor = np.zeros(len(df))
    for col, re, adj in MINOR_GHG:
        if col not in df:
            continue
        base = MINOR_BASE.get(col, 0.0)
        f_minor += (df[col].to_numpy(float) - base) * re * 1e-3 * (1 + adj)

    # --- ozone, excluding the CH4 and temperature terms --------------------
    f_o3 = ((n2o - BASE["n2o"]) * OZONE_RE["n2o"]
            + (eesc - BASE["eesc"]) * OZONE_RE["eesc"]
            + (nox - BASE["nox"]) * OZONE_RE["nox"]
            + (voc - BASE["voc"]) * OZONE_RE["voc"]
            + (co - BASE["co"]) * OZONE_RE["co"])

    # --- aerosols ----------------------------------------------------------
    f_ari = ((so2 - BASE["so2"]) * ERFARI_RE["so2"]
             + (bc - BASE["bc"]) * ERFARI_RE["bc"]
             + (oc - BASE["oc"]) * ERFARI_RE["oc"]
             + (nh3 - BASE["nh3"]) * ERFARI_RE["nh3"]
             + (nox - BASE["nox"]) * ERFARI_RE["nox"]
             + (voc - BASE["voc"]) * ERFARI_RE["voc"]
             + (n2o - BASE["n2o"]) * ERFARI_RE["n2o"]
             + (eesc - BASE["eesc"]) * ERFARI_RE["eesc"])

    def aci_sum(s, b, o):
        return (ACI_SHAPE["so2"] * s + ACI_SHAPE["bc"] * b + ACI_SHAPE["oc"] * o)

    f_aci = ACI_SCALE * (
        np.log1p(aci_sum(so2, bc, oc))
        - np.log1p(aci_sum(BASE["so2"], BASE["bc"], BASE["oc"]))
    )

    f_lapsi = (bc - BASE["bc"]) * LAPSI_RE_BC
    f_albedo = df["RF_albedo"].to_numpy(float) if "RF_albedo" in df else np.zeros(len(df))

    f_other = f_co2 + f_n2o + f_minor + f_o3 + f_ari + f_aci + f_lapsi + f_albedo

    # --- CH4 lifetime scaling from everything except CH4 and temperature ---
    alpha_chem_ext = (
        (1 + (n2o - BASE["n2o"]) * S_N2O_PER_PPB)
        * (1 + (eesc - BASE["eesc"]) * S_EESC_PER_PPT)
        * (1 + (nox - BASE["nox"]) * S_NOX)
        * (1 + (voc - BASE["voc"]) * S_VOC)
    )

    return {
        "f_other": f_other, "alpha_chem_ext": alpha_chem_ext,
        "f_co2": f_co2, "f_n2o": f_n2o, "f_minor": f_minor, "f_o3_ex_ch4": f_o3,
        "f_ari": f_ari, "f_aci": f_aci, "f_lapsi": f_lapsi, "f_albedo": f_albedo,
        "eesc": eesc, "nox_mt_no2": nox, "so2_mt_so2": so2,
    }


# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #

@dataclass
class Params:
    """Everything a dashboard might expose. Defaults are the calibrated set."""

    # --- methane cycle ---
    tau_base: float = 8.25          # CH4 lifetime at the 1750 reference state [yr]
    e_nat: float = 200.0            # natural CH4 emissions at T = 0 [Tg yr-1]
    s_temperature: float = S_TEMPERATURE   # dln(tau)/dT [K-1]; NEGATIVE = damping

    # --- the positive leg of the loop ---
    gamma_wetland: float = 20.0     # extra natural CH4 per K [Tg yr-1 K-1]
    gamma_permafrost: float = 0.0   # additional, if you want it separate

    # --- energy balance (two-layer; Geoffroy et al. 2013 structure) ---
    ecs: float = 3.0                # equilibrium climate sensitivity [K]
    forcing_2co2: float = 3.93      # ERF for doubled CO2 [W m-2], AR6 Ch.7
    c_surface: float = 7.3          # upper-layer heat capacity [W yr m-2 K-1]
    c_deep: float = 106.0           # deep-ocean heat capacity [W yr m-2 K-1]
    kappa: float = 0.677            # heat exchange coefficient [W m-2 K-1]
    epsilon: float = 1.29           # deep-ocean heat uptake efficacy

    # --- other forcing knobs ---
    ozone_temp_feedback: float = OZONE_TEMP_FEEDBACK   # [W m-2 K-1]
    forcing_scale: float = 1.0      # scale non-CH4 forcing (sensitivity tests)

    @property
    def climate_feedback(self):
        """lambda [W m-2 K-1]."""
        return self.forcing_2co2 / self.ecs

    @property
    def tcr(self):
        """Transient climate response [K] implied by the EBM parameters."""
        return self.forcing_2co2 / (self.climate_feedback
                                    + self.epsilon * self.kappa)

    @property
    def gamma_total(self):
        return self.gamma_wetland + self.gamma_permafrost

    def feedback_w_m2_per_k(self, ch4=1900.0, n2o=332.0):
        """gamma_total expressed as W m-2 K-1, for comparison with AR6's
        assessed 0.02-0.09 W m-2 degC-1 non-CO2 biogeochemical feedback.

        A sustained extra E Tg yr-1 raises the steady-state burden by E*tau,
        hence the concentration by E*tau/PPB_TO_TG, hence the forcing by the
        local slope of the CH4 ERF curve including its ozone and H2O terms.
        """
        tau = self.tau_base
        dppb = self.gamma_total * tau / PPB_TO_TG
        slope = ((erf_ch4(ch4 + 0.5, n2o) - erf_ch4(ch4 - 0.5, n2o))
                 + (erf_ch4_extras(ch4 + 0.5) - erf_ch4_extras(ch4 - 0.5)))
        return float(dppb * slope)

    def replace(self, **kw):
        return replace(self, **kw)


# --------------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------------- #

def _rhs(t, y, p, interp):
    """Right-hand side. y = [burden Tg, T surface K, T deep K]."""
    burden, temp, temp_deep = y
    burden = max(burden, 1e-9)
    ch4 = burden / PPB_TO_TG

    e_anth, n2o, f_other, alpha_ext = interp(t)

    # methane lifetime: external chemistry x CH4 self-feedback x temperature
    alpha = (alpha_ext
             * (1.0 + (ch4 - BASE["ch4"]) * S_CH4_PER_PPB)
             * (1.0 + temp * p.s_temperature))
    alpha = max(alpha, 0.05)
    tau = p.tau_base * alpha

    # methane budget, including the warming-driven natural source
    e_natural = p.e_nat + p.gamma_total * temp
    d_burden = e_anth + e_natural - burden / tau

    # forcing
    forcing = (p.forcing_scale * f_other
               + erf_ch4(ch4, n2o) + erf_ch4_extras(ch4)
               + p.ozone_temp_feedback * temp)

    # two-layer energy balance
    d_temp = (forcing - p.climate_feedback * temp
              - p.epsilon * p.kappa * (temp - temp_deep)) / p.c_surface
    d_deep = p.kappa * (temp - temp_deep) / p.c_deep

    return np.array([d_burden, d_temp, d_deep]), tau, forcing, ch4


def _make_interp(years, e_anth, n2o, f_other, alpha_ext):
    yrs = np.asarray(years, float)

    def interp(t):
        return (np.interp(t, yrs, e_anth), np.interp(t, yrs, n2o),
                np.interp(t, yrs, f_other), np.interp(t, yrs, alpha_ext))

    return interp


def run(scenario, params=None, start_year=None, end_year=None,
        substeps=4, c0=None):
    """Integrate the coupled system with fixed-step RK4.

    ``scenario`` is a dict of arrays: year, ch4_emissions, n2o, f_other,
    alpha_chem_ext. Fixed-step RK4 (not solve_ivp) so the JavaScript port can
    reproduce this bit for bit.
    """
    p = params or Params()
    yr = np.asarray(scenario["year"], float)
    i0 = 0 if start_year is None else int(np.searchsorted(yr, start_year))
    i1 = len(yr) - 1 if end_year is None else int(np.searchsorted(yr, end_year))

    interp = _make_interp(yr, scenario["ch4_emissions"], scenario["n2o"],
                          scenario["f_other"], scenario["alpha_chem_ext"])

    # Initial CH4. Default: the prescribed CMIP6 value in start_year, which
    # anchors the run to the real world. Pass c0="steady" for the steady state
    # implied by the parameters instead (fixed-point, since tau depends on CH4).
    if c0 is None and "ch4_cmip6" in scenario:
        c0 = float(np.interp(yr[i0], yr, scenario["ch4_cmip6"]))
    if c0 is None or c0 == "steady":
        e0, _, _, a0 = interp(yr[i0])
        c0 = 700.0
        for _ in range(60):     # fixed point: tau depends on the concentration
            a = a0 * (1.0 + (c0 - BASE["ch4"]) * S_CH4_PER_PPB)
            c0 = (e0 + p.e_nat) * p.tau_base * a / PPB_TO_TG
    y = np.array([c0 * PPB_TO_TG, 0.0, 0.0])

    n = i1 - i0 + 1
    out = {k: np.zeros(n) for k in
           ("year", "ch4", "tau", "forcing", "temperature", "temperature_deep",
            "e_natural", "sink")}
    h = 1.0 / substeps

    for k in range(n):
        t = yr[i0 + k]
        d, tau, forcing, ch4 = _rhs(t, y, p, interp)
        out["year"][k] = t
        out["ch4"][k] = ch4
        out["tau"][k] = tau
        out["forcing"][k] = forcing
        out["temperature"][k] = y[1]
        out["temperature_deep"][k] = y[2]
        out["e_natural"][k] = p.e_nat + p.gamma_total * y[1]
        out["sink"][k] = y[0] / tau
        if k == n - 1:
            break
        for _ in range(substeps):
            k1 = _rhs(t, y, p, interp)[0]
            k2 = _rhs(t + h / 2, y + h / 2 * k1, p, interp)[0]
            k3 = _rhs(t + h / 2, y + h / 2 * k2, p, interp)[0]
            k4 = _rhs(t + h, y + h * k3, p, interp)[0]
            y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            t += h
    return out


def run_with_and_without_feedback(scenario, params=None, **kw):
    """Run twice and difference: the loop's own contribution.

    This is the headline number for a feedback dashboard - how much extra CH4
    and how much extra warming the loop itself produces.
    """
    p = params or Params()
    on = run(scenario, p, **kw)
    off = run(scenario, p.replace(gamma_wetland=0.0, gamma_permafrost=0.0), **kw)
    return {
        "with_feedback": on, "without_feedback": off,
        "delta_ch4": on["ch4"] - off["ch4"],
        "delta_temperature": on["temperature"] - off["temperature"],
        "amplification": np.where(np.abs(off["temperature"]) > 1e-6,
                                  on["temperature"] / np.maximum(off["temperature"], 1e-6),
                                  np.nan),
    }


# --------------------------------------------------------------------------- #
# Scenario loading and calibration
# --------------------------------------------------------------------------- #

SCENARIO_REGISTRY = {
    "ssp119": "SSP1-1.9", "ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0", "ssp434": "SSP4-3.4", "ssp460": "SSP4-6.0",
    "ssp534-over": "SSP5-3.4-over", "ssp585": "SSP5-8.5",
}
_URL = ("https://raw.githubusercontent.com/JGCRI/hector/main/inst/input/tables/"
        "{slug}_emiss-constraints_rf.csv")


def load_raw(slug, cache_dir="data"):
    """Raw Hector/RCMIP scenario table, downloaded once and cached."""
    import os
    import urllib.request
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{slug}.csv")
    if not os.path.exists(path):
        with urllib.request.urlopen(_URL.format(slug=slug), timeout=180) as r:
            body = r.read()
        if len(body) < 1000:
            raise RuntimeError(f"suspiciously small download for {slug!r}")
        open(path, "wb").write(body)
    return pd.read_csv(path, comment=";")


def build_scenario(slug, cache_dir="data"):
    """Everything the coupled model needs for one SSP, as plain arrays."""
    raw = load_raw(slug, cache_dir)
    terms = scenario_forcing_terms(raw)
    return {
        "slug": slug,
        "label": SCENARIO_REGISTRY.get(slug, slug),
        "year": raw["Date"].to_numpy(int),
        "ch4_emissions": raw["CH4_emissions"].to_numpy(float),
        "n2o": raw["N2O_constrain"].to_numpy(float),
        "ch4_cmip6": raw["CH4_constrain"].to_numpy(float),
        "f_other": terms["f_other"],
        "alpha_chem_ext": terms["alpha_chem_ext"],
        "_terms": terms,
        "_raw": raw,
    }


def calibrate(scenarios, params=None, fit=("tau_base", "e_nat"),
              start_year=1750, end_year=2100):
    """Fit chosen parameters so the model reproduces prescribed CMIP6 CH4.

    Done with the wetland feedback OFF, because the CMIP6 concentration
    pathways come from MAGICC7, which holds natural CH4 emissions constant.
    Turning ``gamma_wetland`` on afterwards is then exactly the added feedback
    the dashboard is there to illustrate - not a re-tuning of the baseline.
    """
    from scipy.optimize import least_squares

    p0 = (params or Params()).replace(gamma_wetland=0.0, gamma_permafrost=0.0)
    scen = list(scenarios.values()) if isinstance(scenarios, dict) else list(scenarios)

    def residual(x):
        p = p0.replace(**dict(zip(fit, x)))
        res = []
        for s in scen:
            r = run(s, p, start_year, end_year)
            mask = (s["year"] >= start_year) & (s["year"] <= end_year)
            res.append(r["ch4"] - s["ch4_cmip6"][mask])
        return np.concatenate(res)

    lo = {"tau_base": 4.0, "e_nat": 0.0, "s_temperature": -0.2, "ecs": 1.5}
    hi = {"tau_base": 14.0, "e_nat": 400.0, "s_temperature": 0.0, "ecs": 6.0}
    sol = least_squares(
        residual, np.array([getattr(p0, k) for k in fit], float),
        bounds=([lo[k] for k in fit], [hi[k] for k in fit]),
        x_scale="jac", diff_step=1e-4,
    )
    p_fit = p0.replace(**dict(zip(fit, sol.x)))
    r = sol.fun
    return p_fit, {
        "fitted": {k: float(v) for k, v in zip(fit, sol.x)},
        "rmse_ppb": float(np.sqrt(np.mean(r ** 2))),
        "bias_ppb": float(np.mean(r)),
        "max_abs_ppb": float(np.max(np.abs(r))),
        "window": (start_year, end_year),
        "scenarios": [s["label"] for s in scen],
        "n_points": int(len(r)),
    }


def erf_components_at(scenario, year, params=None, run_out=None):
    """The AR6-comparable ERF breakdown in one year, for verification."""
    p = params or Params()
    t = scenario["_terms"]
    i = int(np.searchsorted(scenario["year"], year))
    if run_out is None:
        run_out = run(scenario, p, 1750, year)
    ch4 = float(run_out["ch4"][-1])
    temp = float(run_out["temperature"][-1])
    n2o = float(scenario["n2o"][i])
    d = ch4 - BASE["ch4"]
    return {
        "CO2": float(t["f_co2"][i]),
        "CH4": float(erf_ch4(ch4, n2o)),
        "N2O": float(t["f_n2o"][i]),
        "halocarbons": float(t["f_minor"][i]),
        "ozone": float(t["f_o3_ex_ch4"][i] + d * OZONE_RE_CH4
                       + p.ozone_temp_feedback * temp),
        "strat. H2O": float(d * H2O_STRAT_CH4),
        "aerosol-radiation": float(t["f_ari"][i] + d * ERFARI_RE_CH4),
        "aerosol-cloud": float(t["f_aci"][i]),
        "BC on snow": float(t["f_lapsi"][i]),
        "land-use albedo": float(t["f_albedo"][i]),
        "TOTAL": float(run_out["forcing"][-1]),
    }
