#!/usr/bin/env python3
"""
build_pattern.py - generate conus-pattern.json: a SYNTHETIC pattern-scaling
field for the contiguous United States, plus state outlines for drawing.

    python3 build_pattern.py

WHAT PATTERN SCALING IS
-----------------------
Local warming is, to a good approximation, proportional to global warming:

    dT(x, y, t)  ~=  P(x, y) * dT_global(t)

P is dimensionless - local kelvin per global kelvin. Real patterns are obtained
by regressing each grid cell's annual-mean temperature on global-mean
temperature across a CMIP6 ensemble (Santer et al. 1990; Mitchell 2003;
Tebaldi & Arblaster 2014; Wells et al. 2023).

*** THE PATTERN IN THIS FILE IS SYNTHETIC. ***
It is NOT derived from CMIP6 output - ESGF is not reachable from the
environment this was written in. It is built from three real physical drivers
with plausible magnitudes, and calibrated to anchor values consistent with
published CMIP6 behaviour:

  1. latitude          - warming increases toward the pole (the tail of polar
                         amplification reaching the northern US)
  2. continentality    - distance to the nearest ocean; land away from water
                         has less thermal inertia to damp it
  3. upwind marine air - distance to ocean looking WEST, because the
                         prevailing mid-latitude westerlies carry Pacific
                         marine air inland, damping the west coast much more
                         strongly than the Atlantic damps the east

The land/ocean mask, the state boundaries and both distance fields are REAL,
computed from Natural Earth 1:50m vectors. Only the mapping from those fields
to P is invented.

Use derive_pattern_from_cmip6.py to replace it with the real thing. That script
emits this same JSON schema, so nothing downstream changes.
"""

import json
import os
import urllib.request

import numpy as np
from matplotlib.path import Path
from scipy.ndimage import distance_transform_edt

NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
      "geojson/{name}")
DATA = "data"

# Wide domain for the distance fields (needs Canada, Mexico and both oceans).
WIDE = dict(lon0=-170.0, lon1=-50.0, lat0=5.0, lat1=80.0, step=0.5)
# Exported CONUS window.
CONUS = dict(lon0=-125.0, lon1=-66.5, lat0=24.0, lat1=49.5, step=0.5)

NON_CONUS = {"Alaska", "Hawaii", "Puerto Rico", "United States Virgin Islands",
             "Guam", "American Samoa", "Northern Mariana Islands",
             "District of Columbia"}   # DC is inside Maryland's outline anyway

# ---------------------------------------------------------------------------
# Anchors: target P values [K per K global]. THESE ARE THE INVENTED PART.
# Chosen to reproduce documented CMIP6 behaviour: a CONUS mean modestly above
# 1, a clear south-to-north gradient, interior exceeding coastal, the Pacific
# coast the most damped, and amplified interior-Southwest warming (AR6 WGII
# Ch.14 notes "continental intensification" and southwestern amplification).
# Edit this table to retune; everything else follows from the fit.
# ---------------------------------------------------------------------------
ANCHORS = [
    # name,                     lat,    lon,     target P
    ("Northern Plains",         47.0, -101.0,   1.42),
    ("Upper Midwest",           45.0,  -90.0,   1.35),
    ("Central Plains",          39.0,  -98.0,   1.32),
    ("Interior Southwest",      35.0, -111.0,   1.28),
    ("Northern Rockies",        45.5, -110.0,   1.38),
    ("Northeast coast",         42.5,  -71.0,   1.14),
    ("Gulf Coast",              30.0,  -90.0,   1.05),
    ("South Florida",           26.0,  -81.0,   0.95),
    ("Coastal California",      36.5, -121.5,   0.92),
    ("Pacific Northwest coast", 47.0, -123.5,   1.05),
    # Interior anchors spanning latitude. Without these the fit satisfies the
    # coastal points by shrinking the marine decay scales to a thin rim, and
    # the interior saturates - the south-to-north gradient vanishes inland,
    # which is not how CMIP6 patterns look.
    ("Southern High Plains",    34.0, -101.5,   1.22),
    ("Interior Deep South",     34.0,  -87.0,   1.15),
    ("Mid-Atlantic interior",   39.5,  -78.5,   1.22),
]


def fetch(name):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        with urllib.request.urlopen(NE.format(name=name), timeout=300) as r:
            body = r.read()
        if len(body) < 10000:
            raise RuntimeError(f"suspiciously small download for {name}")
        open(path, "wb").write(body)
    return json.load(open(path))


def rings(geom):
    """Every exterior ring of a Polygon or MultiPolygon, as an (N,2) array."""
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return []
    return [np.asarray(p[0], float) for p in polys if len(p) and len(p[0]) >= 4]


def grid(spec):
    lon = np.arange(spec["lon0"], spec["lon1"] + 1e-9, spec["step"])
    lat = np.arange(spec["lat0"], spec["lat1"] + 1e-9, spec["step"])
    return lon, lat


def rasterize(all_rings, lon, lat):
    """Boolean mask of points inside any ring. Bounding-box prefilter first."""
    LON, LAT = np.meshgrid(lon, lat)
    pts = np.column_stack([LON.ravel(), LAT.ravel()])
    mask = np.zeros(len(pts), bool)
    for ring in all_rings:
        lo = ring.min(0)
        hi = ring.max(0)
        cand = (~mask
                & (pts[:, 0] >= lo[0]) & (pts[:, 0] <= hi[0])
                & (pts[:, 1] >= lo[1]) & (pts[:, 1] <= hi[1]))
        if not cand.any():
            continue
        idx = np.flatnonzero(cand)
        inside = Path(ring).contains_points(pts[idx])
        mask[idx[inside]] = True
    return mask.reshape(LON.shape)


def distance_to_ocean(land, lon, lat):
    """Great-circle-ish distance [km] from each land cell to the nearest ocean.

    Euclidean transform with anisotropic sampling: the latitude spacing is
    constant in km, the longitude spacing is scaled by cos(mean latitude). An
    approximation across a 75-degree span, and fine for a synthetic field.
    """
    dlat_km = (lat[1] - lat[0]) * 111.32
    dlon_km = (lon[1] - lon[0]) * 111.32 * np.cos(np.deg2rad(lat.mean()))
    return distance_transform_edt(land, sampling=(dlat_km, dlon_km))


def distance_upwind(land, lon, lat):
    """Distance [km] from each land cell to the nearest ocean cell to its WEST.

    One westward scan per latitude row: prevailing westerlies mean marine air
    arrives from the Pacific, which is why the west coast is far more damped
    than the east. Saturates at 6000 km where no ocean lies west in-domain.
    """
    out = np.full(land.shape, 6000.0)
    km_per_cell = (lon[1] - lon[0]) * 111.32 * np.cos(np.deg2rad(lat))[:, None]
    for j in range(land.shape[0]):
        run = np.inf
        for i in range(land.shape[1]):
            if not land[j, i]:
                run = 0.0
            else:
                run = run + 1.0 if np.isfinite(run) else np.inf
            out[j, i] = min(run * km_per_cell[j, 0], 6000.0) if np.isfinite(run) else 6000.0
    return out


#: Marine-influence decay scales [km], fitted by the grid search in main().
#: Ocean air damps warming where it reaches, but it is modified as it is
#: advected over land (and blocked by the Sierra/Cascades), so the influence
#: decays with distance rather than falling off linearly. Using linear terms
#: instead leaves the arid interior Southwest far too cool.
DECAY = {"any": 300.0, "west": 500.0}


def design(lat2d, cont, upw, decay=None):
    """Basis functions for the pattern fit (all dimensionless)."""
    d = decay or DECAY
    dlat = (lat2d - 38.0) / 10.0                   # latitude anomaly per 10 deg
    m_any = np.exp(-cont / d["any"])               # proximity to any ocean
    m_west = np.exp(-upw / d["west"])              # upwind (Pacific) proximity
    return np.stack([np.ones_like(dlat), dlat, m_any, m_west, m_any * dlat], -1)


def main():
    print("loading Natural Earth vectors...")
    countries = fetch("ne_50m_admin_0_countries.geojson")
    states = fetch("ne_50m_admin_1_states_provinces.geojson")

    # ---- wide-domain land mask, for the distance fields -------------------
    wlon, wlat = grid(WIDE)
    land_rings = []
    for f in countries["features"]:
        land_rings += rings(f["geometry"])
    print(f"rasterising land mask on {len(wlon)}x{len(wlat)} grid "
          f"({len(land_rings)} rings)...")
    land = rasterize(land_rings, wlon, wlat)
    print(f"  land fraction {land.mean():.3f}")

    cont_w = distance_to_ocean(land, wlon, wlat)
    upw_w = distance_upwind(land, wlon, wlat)
    print(f"  continentality max {cont_w.max():.0f} km, "
          f"upwind max {upw_w[land].max():.0f} km")

    # ---- CONUS grid and mask ---------------------------------------------
    clon, clat = grid(CONUS)
    conus_rings = []
    for f in states["features"]:
        p = f["properties"]
        if p.get("iso_a2") != "US" or p.get("name") in NON_CONUS:
            continue
        conus_rings += rings(f["geometry"])
    print(f"rasterising CONUS mask on {len(clon)}x{len(clat)} grid "
          f"({len(conus_rings)} rings)...")
    conus = rasterize(conus_rings, clon, clat)
    print(f"  {conus.sum()} land cells")

    # sample the wide-domain distance fields onto the CONUS grid
    def sample(field):
        jj = np.searchsorted(wlat, clat).clip(0, len(wlat) - 1)
        ii = np.searchsorted(wlon, clon).clip(0, len(wlon) - 1)
        return field[np.ix_(jj, ii)]

    cont = sample(cont_w)
    upw = sample(upw_w)
    LAT = np.repeat(clat[:, None], len(clon), 1)

    # ---- fit the pattern to the anchors ----------------------------------
    idxs, targets, names = [], [], []
    for name, alat, alon, target in ANCHORS:
        idxs.append((int(np.abs(clat - alat).argmin()),
                     int(np.abs(clon - alon).argmin())))
        targets.append(target)
        names.append(name)
    b = np.asarray(targets)

    def fit(decay):
        rows = [design(LAT[j:j + 1, i:i + 1], cont[j:j + 1, i:i + 1],
                       upw[j:j + 1, i:i + 1], decay).reshape(-1)
                for j, i in idxs]
        A = np.asarray(rows)
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        return coef, A, float(np.sqrt(np.mean((A @ coef - b) ** 2)))

    # small grid search over the two decay scales
    best = None
    # Bounded to physically defensible scales: marine air is modified over a
    # few hundred km, and the Sierra/Cascade barrier sits 200-400 km inland.
    # Letting the search go lower buys a smaller anchor RMS by destroying the
    # interior gradient.
    for la in (200, 250, 300, 350, 400, 500, 600):
        for lw in (300, 400, 500, 600, 750, 900):
            coef, A, rms = fit({"any": float(la), "west": float(lw)})
            if best is None or rms < best[0]:
                best = (rms, {"any": float(la), "west": float(lw)}, coef, A)
    rms, decay, coef, A = best
    print(f"\nfitted decay scales: any-ocean {decay['any']:.0f} km, "
          f"upwind {decay['west']:.0f} km  (RMS {rms:.4f})")

    pattern = design(LAT, cont, upw, decay) @ coef
    pattern = np.where(conus, pattern, np.nan)

    print("\nanchor fit:")
    fitted = A @ coef
    for name, t, f in zip(names, b, fitted):
        print(f"  {name:24s} target {t:.2f}  fitted {f:.2f}  "
              f"resid {f - t:+.3f}")
    print(f"  RMS residual {np.sqrt(np.mean((fitted - b) ** 2)):.4f}")

    # area weighting: cell area scales with cos(latitude)
    w = np.repeat(np.cos(np.deg2rad(clat))[:, None], len(clon), 1)
    ok = np.isfinite(pattern)
    mean_p = float((pattern[ok] * w[ok]).sum() / w[ok].sum())
    print(f"\narea-weighted CONUS mean P = {mean_p:.3f} K per K global")
    print(f"range {np.nanmin(pattern):.2f} to {np.nanmax(pattern):.2f}")

    np.save("_pattern.npy", pattern)
    np.save("_conus.npy", conus)
    json.dump({"lon": clon.tolist(), "lat": clat.tolist(),
               "coef": coef.tolist(), "decay": decay, "mean_p": mean_p,
               "anchor_rms": rms,
               "anchors": [[n, la, lo, t, float(f)]
                           for (n, la, lo, t), f in zip(ANCHORS, A @ coef)]},
              open("_pattern_meta.json", "w"))
    print("\nwrote _pattern.npy, _conus.npy, _pattern_meta.json")


if __name__ == "__main__":
    main()
