#!/usr/bin/env python3
"""
test_ingest.py - verify derive_pattern_from_cmip6.py recovers a KNOWN pattern.

    python3 test_ingest.py

Builds CMIP6-shaped synthetic NetCDF files (monthly `tas`, 0-360 longitude, a
realistic coarse grid) in which the true pattern P is imposed exactly, then
checks the script's regression gets it back. Run this before trusting the
script on real data - it tests the regression, the area weighting, the annual
aggregation, the longitude wrap and the CONUS interpolation.
"""
import os
import shutil
import tempfile

import numpy as np
import xarray as xr

import derive_pattern_from_cmip6 as mod


def make_dataset(path, years=(1850, 2100), nlat=144, nlon=192, seed=0,
                 noise_K=0.0):
    """CMIP6-shaped tas with an imposed pattern whose global mean is exactly 1."""
    rng = np.random.default_rng(seed)
    lat = np.linspace(-89.375, 89.375, nlat)
    lon = np.linspace(0.9375, 359.0625, nlon)

    # a smooth "true" pattern: land-like amplification plus a latitude gradient
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    P = (1.0 + 0.9 * (np.abs(LAT) / 90.0) ** 1.5
         + 0.25 * np.cos(np.deg2rad(2 * LON))
         + 0.15 * np.sin(np.deg2rad(LAT * 3)))
    # normalise so the AREA-WEIGHTED global mean of P is exactly 1; then the
    # global-mean anomaly of the synthetic field equals the imposed forcing.
    w = np.cos(np.deg2rad(LAT))
    P = P / ((P * w).sum() / w.sum())

    n_year = years[1] - years[0] + 1
    time = xr.cftime_range(f"{years[0]}-01-01", periods=n_year * 12, freq="MS",
                           calendar="noleap")
    yr_index = np.repeat(np.arange(n_year), 12)

    # global anomaly: a non-linear ramp, so the fit is not trivially exact
    g_ann = 4.0 * (np.arange(n_year) / (n_year - 1)) ** 1.6
    g_ann += 0.05 * rng.standard_normal(n_year)      # interannual wobble
    g = g_ann[yr_index]

    clim = 288.0 + 30.0 * np.cos(np.deg2rad(LAT))     # static climatology
    seasonal = 8.0 * np.sin(np.deg2rad(LAT))[None, :, :] * \
        np.cos(2 * np.pi * (np.arange(len(time)) % 12) / 12)[:, None, None]

    tas = (clim[None] + seasonal + P[None] * g[:, None, None])
    if noise_K:
        tas = tas + noise_K * rng.standard_normal(tas.shape)

    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), tas.astype("float32"))},
        coords={"time": time, "lat": lat, "lon": lon},
    )
    ds.tas.attrs.update(units="K", standard_name="air_temperature")
    ds.to_netcdf(path)
    return P, g_ann, lat, lon


def main():
    tmp = tempfile.mkdtemp(prefix="cmip6test_")
    checks, failures = 0, 0

    def check(name, ok, detail=""):
        nonlocal checks, failures
        checks += 1
        if ok:
            print(f"  pass {name}{'  -> ' + detail if detail else ''}")
        else:
            failures += 1
            print(f"  FAIL {name}  {detail}")

    try:
        # ---------------- noiseless: recovery should be near-exact ----------
        print("noiseless case:")
        path = os.path.join(tmp, "tas_test_noiseless.nc")
        P_true, g_ann, lat, lon = make_dataset(path, noise_K=0.0)
        P_hat, hlat, hlon, diag = mod.derive(path, ref=(1850, 1900))

        err = np.abs(P_hat - P_true)
        w = np.cos(np.deg2rad(np.meshgrid(lat, lon, indexing="ij")[0]))
        wmae = float((err * w).sum() / w.sum())
        check("recovers the imposed pattern", err.max() < 0.02,
              f"max error {err.max():.2e}, area-weighted MAE {wmae:.2e}")
        check("R^2 near 1", diag["median_r2"] > 0.999,
              f"median R^2 {diag['median_r2']:.6f}")
        check("global-mean pattern is 1 by construction",
              abs((P_hat * w).sum() / w.sum() - 1.0) < 1e-3,
              f"{(P_hat * w).sum() / w.sum():.6f}")
        check("longitude converted to -180..180",
              hlon.min() < 0 and hlon.max() <= 180,
              f"{hlon.min():.1f} to {hlon.max():.1f}")

        # ---------------- noisy: should still be close ----------------------
        print("\nwith 0.3 K of grid-cell noise:")
        path2 = os.path.join(tmp, "tas_test_noisy.nc")
        P_true2, _, _, _ = make_dataset(path2, seed=7, noise_K=0.3)
        P_hat2, _, _, diag2 = mod.derive(path2, ref=(1850, 1900))
        err2 = np.abs(P_hat2 - P_true2)
        check("noise-robust", np.median(err2) < 0.02,
              f"median error {np.median(err2):.4f}, max {err2.max():.4f}")
        check("R^2 degrades but stays high", 0.8 < diag2["median_r2"] < 1.0,
              f"median R^2 {diag2['median_r2']:.4f}")

        # ---------------- intercept diagnostic -----------------------------
        print("\nintercept diagnostic:")
        P_hat3, _, _, diag3 = mod.derive(path, ref=(1850, 1900),
                                         with_intercept=True)
        check("fitted intercept is negligible for a linear field",
              diag3["max_abs_intercept_K"] < 0.05,
              f"max |intercept| {diag3['max_abs_intercept_K']:.4f} K")
        check("intercept fit agrees with through-origin fit",
              np.abs(P_hat3 - P_hat).max() < 0.02,
              f"max difference {np.abs(P_hat3 - P_hat).max():.2e}")

        # ---------------- CONUS interpolation ------------------------------
        print("\nCONUS interpolation:")
        Pc, clon, clat = mod.to_conus(P_hat, hlat, hlon)
        check("CONUS grid shape", Pc.shape == (len(clat), len(clon)),
              f"{Pc.shape}")
        check("no NaNs inside the window", np.isfinite(Pc).all(),
              f"{int(np.isfinite(Pc).sum())}/{Pc.size} finite")
        # spot-check interpolation against the source field at a grid point
        j = int(np.abs(hlat - clat[20]).argmin())
        i = int(np.abs(hlon - clon[40]).argmin())
        near = mod.to_conus(P_hat, hlat, hlon)[0][20, 40]
        check("interpolation is bounded by the source field",
              P_hat.min() - 1e-6 <= near <= P_hat.max() + 1e-6,
              f"interpolated {near:.4f} within [{P_hat.min():.3f}, "
              f"{P_hat.max():.3f}]")

        # ---------------- reference-period guard ---------------------------
        print("\nerror handling:")
        try:
            mod.derive(path, ref=(2200, 2250))
            check("rejects an uncovered reference period", False, "no error raised")
        except SystemExit as e:
            check("rejects an uncovered reference period", True,
                  str(e).split(".")[0][:60])

        print(f"\n{checks - failures}/{checks} checks passed")
        if failures:
            raise SystemExit(f"{failures} FAILURES")
        print("derive_pattern_from_cmip6.py recovers a known pattern correctly.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
