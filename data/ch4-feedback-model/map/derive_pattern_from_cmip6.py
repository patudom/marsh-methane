#!/usr/bin/env python3
"""
derive_pattern_from_cmip6.py - replace the synthetic pattern with a real one,
derived from CMIP6 `tas` output.

    pip install xarray netCDF4 scipy numpy matplotlib   # + dask for large ensembles
    python3 derive_pattern_from_cmip6.py --files 'cmip6/tas_*.nc' --model ACCESS-CM2
    python3 export_bundle.py --pattern real_pattern.npz      # rebuild the JSON

WHAT THIS DOES
--------------
Pattern scaling, the standard way (Santer et al. 1990; Mitchell 2003;
Tebaldi & Arblaster 2014; Wells et al. 2023):

  1. annual-mean `tas` per grid cell
  2. area-weighted global annual-mean `tas` (cos-latitude weights)
  3. anomalies for both, relative to a reference period (default 1850-1900)
  4. per-grid-cell ordinary least squares of local anomaly on global anomaly;
     the SLOPE is P(x, y)
  5. bilinear interpolation onto the CONUS grid, then the CONUS land mask
  6. optional multi-model mean of P (average the patterns, never the raw
     fields - models have different grids and different global warming)

Regression through the origin is the right choice: at zero global anomaly the
local anomaly must also be zero by construction of the anomaly. Pass
--with-intercept to fit one anyway and inspect it as a diagnostic - a large
intercept means the linear assumption is straining.

GETTING THE DATA
----------------
ESGF web search:
    https://esgf-node.llnl.gov/search/cmip6/
    variable=tas  frequency=mon  experiment_id=historical,ssp245  variant_label=r1i1p1f1

Or from the Pangeo cloud catalogue, no downloads:
    import intake
    cat = intake.open_esm_datastore(
        "https://storage.googleapis.com/cmip6/pangeo-cmip6.json")
    sub = cat.search(variable_id="tas", table_id="Amon",
                     experiment_id=["historical", "ssp245"],
                     member_id="r1i1p1f1", source_id="ACCESS-CM2")
    dsets = sub.to_dataset_dict()

Concatenate historical with the scenario so the regression spans a wide range
of global warming - that is what makes the slope well determined. A single
scenario's own span works, but a longer lever arm is better.

WHICH MODELS
------------
Use several. Inter-model spread in P is larger than inter-scenario spread
(Wells et al. 2023), so a single model's pattern is not "the" pattern. Five or
more members of the CMIP6 ensemble, averaged, is a defensible choice; report
the spread alongside the mean.
"""

import argparse
import glob
import json

import numpy as np

CONUS = dict(lon0=-125.0, lon1=-66.5, lat0=24.0, lat1=49.5, step=0.5)


def to_180(lon):
    """CMIP6 usually uses 0..360; the CONUS window needs -180..180."""
    return ((np.asarray(lon, float) + 180.0) % 360.0) - 180.0


def annual_mean(da):
    """Monthly -> annual mean, weighted by days in month."""
    import xarray as xr
    days = da["time"].dt.days_in_month
    return (da * days).groupby("time.year").sum("time") / \
        days.groupby("time.year").sum("time")


def global_mean(da, lat_name="lat"):
    """Area-weighted global mean (cos-latitude)."""
    w = np.cos(np.deg2rad(da[lat_name]))
    return da.weighted(w).mean(dim=[d for d in da.dims if d != "year"])


def _time_kwargs():
    """cftime decoding, across the xarray API change.

    CMIP6 uses non-standard calendars (noleap, 360_day), so times must be
    decoded to cftime objects rather than numpy datetime64. Newer xarray wants
    a coder object; older takes use_cftime=True.
    """
    import xarray as xr
    coders = getattr(xr, "coders", None)
    if coders is not None and hasattr(coders, "CFDatetimeCoder"):
        return {"decode_times": coders.CFDatetimeCoder(use_cftime=True)}
    return {"use_cftime": True}


def load_tas(pattern_glob):
    """Open one or more tas files. Chunks via dask when it is available -
    real CMIP6 files are large - but works without it."""
    import xarray as xr
    files = sorted(glob.glob(pattern_glob))
    if not files:
        raise SystemExit(f"no files matched {pattern_glob!r}")
    print(f"  {len(files)} file(s)")

    kw = dict(combine="by_coords", **_time_kwargs())
    try:
        import dask  # noqa: F401
        ds = xr.open_mfdataset(files, chunks={"time": 120}, **kw)
    except ImportError:
        if len(files) == 1:
            ds = xr.open_dataset(files[0], **_time_kwargs())
        else:
            ds = xr.open_mfdataset(files, **kw)
        print("  (dask not installed - reading eagerly; "
              "pip install dask for large ensembles)")
    if "tas" not in ds:
        raise SystemExit(f"no 'tas' variable; found {list(ds.data_vars)}")
    return ds["tas"]


def derive(pattern_glob, ref=(1850, 1900), with_intercept=False):
    """-> (P on the model's native grid, lat, lon, diagnostics)"""
    print(f"opening {pattern_glob}")
    tas = load_tas(pattern_glob)
    lat_name = "lat" if "lat" in tas.dims else "latitude"
    lon_name = "lon" if "lon" in tas.dims else "longitude"

    print("  annual means...")
    ann = annual_mean(tas).compute()
    glob_ann = global_mean(ann, lat_name).compute()

    sel = (ann["year"] >= ref[0]) & (ann["year"] <= ref[1])
    if not bool(sel.any()):
        raise SystemExit(
            f"reference period {ref} not covered "
            f"({int(ann['year'].min())}-{int(ann['year'].max())}). "
            "Include the historical run, or pass --ref.")
    local_ref = ann.isel(year=np.flatnonzero(sel.values)).mean("year")
    glob_ref = float(glob_ann.isel(year=np.flatnonzero(sel.values)).mean())

    local_anom = (ann - local_ref).transpose("year", lat_name, lon_name).values
    glob_anom = (glob_ann - glob_ref).values
    n_year = len(glob_anom)
    print(f"  {n_year} years, global anomaly span "
          f"{glob_anom.min():+.2f} to {glob_anom.max():+.2f} K")

    Y = local_anom.reshape(n_year, -1)
    x = glob_anom
    good = np.isfinite(x) & np.isfinite(Y).all(1)
    x, Y = x[good], Y[good]

    if with_intercept:
        A = np.column_stack([x, np.ones_like(x)])
        sol, *_ = np.linalg.lstsq(A, Y, rcond=None)
        slope, intercept = sol[0], sol[1]
    else:
        # through the origin: slope = <x,y> / <x,x>
        slope = (x @ Y) / (x @ x)
        intercept = np.zeros_like(slope)

    resid = Y - np.outer(x, slope) - intercept
    ss_res = (resid ** 2).sum(0)
    ss_tot = ((Y - Y.mean(0)) ** 2).sum(0)
    r2 = np.where(ss_tot > 0, 1 - ss_res / ss_tot, np.nan)

    shape = local_anom.shape[1:]
    diag = {
        "n_years": int(len(x)),
        "global_span_K": [float(x.min()), float(x.max())],
        "reference_period": list(ref),
        "through_origin": not with_intercept,
        "median_r2": float(np.nanmedian(r2)),
        "rmse_K": float(np.sqrt(np.nanmean(ss_res / max(len(x), 1)))),
        "max_abs_intercept_K": float(np.nanmax(np.abs(intercept))),
    }
    print(f"  median R^2 {diag['median_r2']:.4f}, residual RMSE "
          f"{diag['rmse_K']:.3f} K")
    if with_intercept:
        print(f"  max |intercept| {diag['max_abs_intercept_K']:.3f} K")
    return (slope.reshape(shape), tas[lat_name].values,
            to_180(tas[lon_name].values), diag)


def to_conus(P, lat, lon):
    """Bilinear interpolation onto the CONUS grid, handling the dateline seam."""
    from scipy.interpolate import RegularGridInterpolator

    order = np.argsort(lon)
    lon_s, P_s = lon[order], P[:, order]
    if lat[0] > lat[-1]:
        lat, P_s = lat[::-1], P_s[::-1, :]
    # pad longitude so the CONUS window never falls outside the domain
    lon_p = np.concatenate([lon_s[-1:] - 360, lon_s, lon_s[:1] + 360])
    P_p = np.concatenate([P_s[:, -1:], P_s, P_s[:, :1]], axis=1)

    f = RegularGridInterpolator((lat, lon_p), P_p, method="linear",
                                bounds_error=False, fill_value=np.nan)
    clon = np.arange(CONUS["lon0"], CONUS["lon1"] + 1e-9, CONUS["step"])
    clat = np.arange(CONUS["lat0"], CONUS["lat1"] + 1e-9, CONUS["step"])
    LAT, LON = np.meshgrid(clat, clon, indexing="ij")
    return f(np.stack([LAT.ravel(), LON.ravel()], -1)).reshape(LAT.shape), clon, clat


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", action="append", required=True,
                    help="glob of tas NetCDF files; repeat once per model")
    ap.add_argument("--model", action="append", default=None,
                    help="model label, in the same order as --files")
    ap.add_argument("--ref", nargs=2, type=int, default=(1850, 1900),
                    metavar=("Y0", "Y1"), help="reference period")
    ap.add_argument("--with-intercept", action="store_true",
                    help="fit an intercept as a linearity diagnostic")
    ap.add_argument("--out", default="real_pattern.npz")
    args = ap.parse_args()

    labels = args.model or [f"model{i}" for i in range(len(args.files))]
    if len(labels) != len(args.files):
        raise SystemExit("--model must be given once per --files")

    stack, diags = [], {}
    for label, g in zip(labels, args.files):
        print(f"\n=== {label} ===")
        P, lat, lon, diag = derive(g, tuple(args.ref), args.with_intercept)
        Pc, clon, clat = to_conus(P, lat, lon)
        print(f"  CONUS-grid P range {np.nanmin(Pc):.3f} to {np.nanmax(Pc):.3f}")
        stack.append(Pc)
        diags[label] = diag

    stack = np.asarray(stack)
    mean = np.nanmean(stack, 0)
    spread = np.nanstd(stack, 0) if len(stack) > 1 else np.zeros_like(mean)

    # apply the CONUS land mask produced by build_pattern.py
    try:
        conus = np.load("_conus.npy")
        mean = np.where(conus, mean, np.nan)
        spread = np.where(conus, spread, np.nan)
        print("\napplied the CONUS land mask from _conus.npy")
    except FileNotFoundError:
        print("\n_conus.npy not found - run build_pattern.py first to get the "
              "land mask, or the pattern will include ocean and Canada")

    w = np.repeat(np.cos(np.deg2rad(clat))[:, None], len(clon), 1)
    ok = np.isfinite(mean)
    print(f"area-weighted CONUS mean P = "
          f"{(mean[ok] * w[ok]).sum() / w[ok].sum():.3f} K per K global")
    if len(stack) > 1:
        print(f"inter-model spread (1 sigma): mean {np.nanmean(spread):.3f}, "
              f"max {np.nanmax(spread):.3f}")

    np.savez(args.out, pattern=mean, spread=spread, lon=clon, lat=clat,
             models=np.array(labels), diagnostics=json.dumps(diags))
    print(f"\nwrote {args.out}")
    print("next:  python3 export_bundle.py --pattern " + args.out)


if __name__ == "__main__":
    main()
