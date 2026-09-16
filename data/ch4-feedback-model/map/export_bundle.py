#!/usr/bin/env python3
"""
export_bundle.py - turn the fitted pattern into conus-pattern.json for the
browser, together with simplified state outlines and a validated diverging
colour ramp.

    python3 build_pattern.py && python3 export_bundle.py
"""
import json

import numpy as np

# --------------------------------------------------------------------------- #
# OKLab, for building and checking the colour ramp
# --------------------------------------------------------------------------- #

def _srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def hex_to_oklab(h):
    rgb = np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    lms = _M1 @ _srgb_to_linear(rgb)
    return _M2 @ np.cbrt(lms)


def oklab_to_hex(lab):
    lms = np.linalg.solve(_M2, np.asarray(lab, float)) ** 3
    rgb = _linear_to_srgb(np.linalg.solve(_M1, lms))
    v = np.clip(np.round(rgb * 255), 0, 255).astype(int)
    return "#%02x%02x%02x" % tuple(v)


def oklab_to_lch(lab):
    L, a, b = lab
    return L, float(np.hypot(a, b)), float(np.arctan2(b, a))


def lch_to_oklab(L, C, h):
    return np.array([L, C * np.cos(h), C * np.sin(h)])


#: Documented blue ramp (dataviz reference palette), light -> dark.
BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
             "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
             "#0d366b"]
#: Documented diverging poles and neutral midpoint.
RED_ANCHOR = "#e34948"
MID_LIGHT = "#f0efec"
MID_DARK = "#383835"


def build_diverging(n_arm=8, mid=MID_LIGHT):
    """Diverging ramp: blue (cool) <-> gray midpoint <-> red (warm).

    The cool arm walks the DOCUMENTED blue ramp. The warm arm is generated at
    red's OKLCH hue with the cool arm's lightness and chroma profile mirrored,
    so the two arms are perceptually balanced - neither side looks heavier.
    """
    # cool arm: midpoint outward to the darkest blue
    picks = np.linspace(2, len(BLUE_RAMP) - 1, n_arm).round().astype(int)
    cool = [BLUE_RAMP[i] for i in picks]                 # light -> dark
    cool_lab = [hex_to_oklab(h) for h in cool]

    _, _, red_h = oklab_to_lch(hex_to_oklab(RED_ANCHOR))
    warm = []
    for lab in cool_lab:
        L, C, _ = oklab_to_lch(lab)
        warm.append(oklab_to_hex(lch_to_oklab(L, C, red_h)))

    # full ramp, cool-dark ... mid ... warm-dark
    return list(reversed(cool)) + [mid] + warm


def check_ramp(ramp):
    """A diverging ramp must have monotone lightness on each arm and
    symmetric arms. (The categorical CVD validator FAILS on value ramps by
    design - lightness monotonicity is the right check here.)"""
    L = [oklab_to_lch(hex_to_oklab(h))[0] for h in ramp]
    mid = len(ramp) // 2
    cool, warm = L[:mid + 1], L[mid:]
    ok_cool = all(b > a - 1e-9 for a, b in zip(cool, cool[1:]))   # rising to mid
    ok_warm = all(b < a + 1e-9 for a, b in zip(warm, warm[1:]))   # falling after
    asym = max(abs(cool[i] - warm[len(warm) - 1 - i]) for i in range(len(cool)))
    return {"monotone_cool": ok_cool, "monotone_warm": ok_warm,
            "max_arm_asymmetry_L": round(float(asym), 5),
            "lightness": [round(float(x), 4) for x in L]}


# --------------------------------------------------------------------------- #
# Outline simplification
# --------------------------------------------------------------------------- #

def simplify(ring, tol_deg):
    """Radial-distance decimation: drop points closer than tol to the last kept."""
    out = [ring[0]]
    for p in ring[1:-1]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= tol_deg:
            out.append(p)
    out.append(ring[-1])
    return out


def ring_extent(ring):
    a = np.asarray(ring, float)
    return (a[:, 0].max() - a[:, 0].min()) + (a[:, 1].max() - a[:, 1].min())


NON_CONUS = {"Alaska", "Hawaii", "Puerto Rico", "United States Virgin Islands",
             "Guam", "American Samoa", "Northern Mariana Islands",
             "District of Columbia"}


def outlines(tol=0.09, min_extent=0.6):
    src = json.load(open("data/ne_50m_admin_1_states_provinces.geojson"))
    states = []
    for f in src["features"]:
        p = f["properties"]
        if p.get("iso_a2") != "US" or p.get("name") in NON_CONUS:
            continue
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        parts = []
        for poly in polys:
            ring = poly[0]
            if len(ring) < 4 or ring_extent(ring) < min_extent:
                continue            # drop offshore islands and slivers
            s = simplify(ring, tol)
            parts.append([[round(x, 3), round(y, 3)] for x, y in s])
        if parts:
            states.append({"name": p.get("name"),
                           "code": (p.get("postal") or p.get("iso_3166_2", "")[-2:]),
                           "rings": parts})
    return states


# --------------------------------------------------------------------------- #

def state_index(lon, lat, states, finite):
    """Per-grid-cell state assignment, so a dashboard can report per-state
    means without shipping polygons to the client for point-in-polygon."""
    from matplotlib.path import Path
    LON, LAT = np.meshgrid(lon, lat)
    pts = np.column_stack([LON.ravel(), LAT.ravel()])
    idx = np.full(len(pts), -1, int)
    for k, st in enumerate(states):
        for ring in st["rings"]:
            r = np.asarray(ring, float)
            lo, hi = r.min(0), r.max(0)
            cand = ((idx < 0)
                    & (pts[:, 0] >= lo[0]) & (pts[:, 0] <= hi[0])
                    & (pts[:, 1] >= lo[1]) & (pts[:, 1] <= hi[1]))
            if not cand.any():
                continue
            j = np.flatnonzero(cand)
            inside = Path(r).contains_points(pts[j])
            idx[j[inside]] = k
    idx = np.where(finite.ravel(), idx, -1)
    # nearest-state fill for land cells the simplified rings missed
    missing = np.flatnonzero((idx < 0) & finite.ravel())
    have = np.flatnonzero(idx >= 0)
    if len(missing) and len(have):
        for m in missing:
            d = np.hypot(pts[have, 0] - pts[m, 0], pts[have, 1] - pts[m, 1])
            idx[m] = idx[have[int(d.argmin())]]
    return idx


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default=None,
                    help="real_pattern.npz from derive_pattern_from_cmip6.py; "
                         "omit to use the synthetic _pattern.npy")
    ap.add_argument("--out", default="conus-pattern.json")
    args = ap.parse_args()

    synthetic = args.pattern is None
    if synthetic:
        pattern = np.load("_pattern.npy")
        meta = json.load(open("_pattern_meta.json"))
        lon = np.asarray(meta["lon"], float)
        lat = np.asarray(meta["lat"], float)
        real_info = None
    else:
        z = np.load(args.pattern, allow_pickle=False)
        pattern = z["pattern"]
        lon = z["lon"]
        lat = z["lat"]
        real_info = {
            "models": [str(m) for m in z["models"]],
            "diagnostics": json.loads(str(z["diagnostics"])),
            "inter_model_spread_mean": (
                round(float(np.nanmean(z["spread"])), 4)
                if "spread" in z else None),
            "inter_model_spread_max": (
                round(float(np.nanmax(z["spread"])), 4)
                if "spread" in z else None),
        }
        meta = {"anchor_rms": 0.0, "decay": {}, "coef": [],
                "anchors": []}
        print(f"using REAL pattern from {args.pattern}: "
              f"{', '.join(real_info['models'])}")

    ramp = build_diverging()
    ramp_check = check_ramp(ramp)
    # The warm arm on its own is the SEQUENTIAL ramp, for fields that never
    # cross zero. Warming-since-today is all-positive under most scenarios, so
    # a diverging scale there wastes half its range and flattens the spatial
    # structure; sequential is the correct encoding for a magnitude.
    mid = len(ramp) // 2
    sequential = ramp[mid:]
    seq_L = [oklab_to_lch(hex_to_oklab(h))[0] for h in sequential]
    assert all(b < a + 1e-9 for a, b in zip(seq_L, seq_L[1:])), seq_L
    assert ramp_check["monotone_cool"] and ramp_check["monotone_warm"], ramp_check
    print(f"diverging ramp: {len(ramp)} steps, arm asymmetry "
          f"{ramp_check['max_arm_asymmetry_L']:.2e} (lightness monotone: ok)")
    print(f"sequential ramp: {len(sequential)} steps, lightness monotone: ok")

    states = outlines()
    n_pts = sum(len(r) for s in states for r in s["rings"])
    print(f"outlines: {len(states)} states, {n_pts} points after simplification")

    finite = np.isfinite(pattern)
    sidx = state_index(lon, lat, states, finite)
    assigned = int((sidx >= 0).sum())
    print(f"state index: {assigned}/{int(finite.sum())} land cells assigned")
    w = np.repeat(np.cos(np.deg2rad(lat))[:, None], len(lon), 1)
    flat = np.where(finite, pattern, -9999.0).round(4)

    bundle = {
        "meta": {
            "title": ("CONUS pattern-scaling field (SYNTHETIC)" if synthetic
                      else "CONUS pattern-scaling field (CMIP6-derived)"),
            "synthetic": synthetic,
            "cmip6": real_info,
            "warning": ((
                "THIS PATTERN IS SYNTHETIC. It is not derived from CMIP6 "
                "output. The land/ocean mask, state boundaries and both "
                "distance fields are real (Natural Earth 1:50m); the mapping "
                "from them to P is invented and calibrated to anchor values "
                "chosen to be consistent with published CMIP6 behaviour. "
                "Replace it with derive_pattern_from_cmip6.py before using "
                "any of this to make a claim about the real world.")
                if synthetic else
                "Derived from CMIP6 tas by per-gridcell regression. Pattern "
                "scaling remains a linear approximation - see limits."),
            "method": (
                "Pattern scaling: dT(x,y,t) = P(x,y) * dT_global(t). Real "
                "patterns come from per-gridcell linear regression of local "
                "annual-mean temperature on global-mean temperature "
                "(Santer et al. 1990; Tebaldi & Arblaster 2014; "
                "Wells et al. 2023, ESD 14, 817)."),
            "units": {"pattern": "K local per K global mean (dimensionless)",
                      "lat": "degrees north", "lon": "degrees east"},
            "nodata": -9999.0,
            "grid": {"nlon": len(lon), "nlat": len(lat),
                     "lon0": float(lon[0]), "lat0": float(lat[0]),
                     "step": float(round(lon[1] - lon[0], 6))},
            "limits": (
                "Pattern scaling is a linear approximation. Self-emulation "
                "errors are typically under 0.3 K, but out-of-sample errors "
                "exceed 0.5 K in the Northern Hemisphere mid-latitudes - "
                "which includes CONUS. It degrades most for strong-mitigation "
                "and overshoot pathways (20-50% time-series error, because "
                "regions peak at different times than the global mean) and "
                "where aerosol forcing patterns change. It does not represent "
                "internal variability at all: these are forced-response "
                "fields, not weather."),
        },
        "calibration": {
            "anchor_rms": round(float(meta["anchor_rms"]), 4),
            "decay_km": meta["decay"],
            "coefficients": [round(float(c), 6) for c in meta["coef"]],
            "basis": ["1", "(lat-38)/10", "exp(-d_ocean/L_any)",
                      "exp(-d_upwind/L_west)", "exp(-d_ocean/L_any)*(lat-38)/10"],
            "anchors": [{"name": n, "lat": la, "lon": lo,
                         "target": t, "fitted": round(float(f), 4)}
                        for n, la, lo, t, f in meta["anchors"]],
            "known_residuals": (
                "The interior Southwest fits about 0.06 low and the interior "
                "Deep South about 0.06 high. Both are aridity effects - dry "
                "soil cannot evaporatively cool, so arid regions warm more - "
                "and there is no aridity term in the basis because that would "
                "mean inventing a second layer of structure on top of an "
                "already synthetic field. Real CMIP6 data is the fix."),
            "area_weighted_mean": round(float(
                (pattern[finite] * w[finite]).sum() / w[finite].sum()), 4),
            "min": round(float(np.nanmin(pattern)), 4),
            "max": round(float(np.nanmax(pattern)), 4),
        },
        "lat": [round(float(v), 4) for v in lat],
        "lon": [round(float(v), 4) for v in lon],
        "pattern": [float(v) for v in flat.ravel()],   # row-major, lat then lon
        "state_index": [int(v) for v in sidx],
        "state_names": [s["name"] for s in states],
        "ramp": {"diverging": ramp, "sequential": sequential,
                 "sequential_note": ("light->dark warm ramp, the warm arm of "
                                     "the diverging ramp; use for fields that "
                                     "do not cross zero"), "midpoint_light": MID_LIGHT,
                 "midpoint_dark": MID_DARK, "check": ramp_check},
        "outlines": states,
    }

    if synthetic:
        bundle["calibration"]["synthetic_note"] = (
            "anchor_rms, decay_km, coefficients and anchors describe the "
            "SYNTHETIC fit and are absent for a CMIP6-derived pattern.")
    txt = json.dumps(bundle, separators=(",", ":"))
    open(args.out, "w").write(txt)
    print(f"wrote {args.out} ({len(txt) / 1024:.0f} KB)"
          + ("  [SYNTHETIC]" if synthetic else "  [CMIP6-derived]"))
    print(f"  grid {len(lon)}x{len(lat)}, {int(finite.sum())} land cells, "
          f"P in [{bundle['calibration']['min']}, {bundle['calibration']['max']}], "
          f"mean {bundle['calibration']['area_weighted_mean']}")


if __name__ == "__main__":
    main()
