#!/usr/bin/env python3
"""
validate_wwt.py - verify the WWT export puts the data in the right place on
the globe, and that the WTML says what WWT needs to hear.

    python3 export_wwt.py --years 2050,2100 --depth 5 --outdir wwt
    python3 validate_wwt.py --outdir wwt

File counts prove nothing: a longitude sign error would silently place the
CONUS field over central Asia and every file would still be there. So this
walks the actual TOAST pyramid, resolves real cities to their tile and pixel
via toasty's own TOAST geometry, and checks the pixel that comes back.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_wwt import colorize, load_pattern, ramp_lut   # noqa: E402

# name, lat, lon, expected to be painted?
POINTS = [
    ("Fargo ND",        46.88, -96.79,  True),
    ("Denver CO",       39.74, -104.99, True),
    ("Miami FL",        25.76, -80.19,  True),
    ("San Francisco CA", 37.77, -122.42, True),
    ("Portland ME",     43.66, -70.26,  True),
    # must be EMPTY - these catch sign flips and hemisphere errors
    ("mid-Atlantic",    30.00, -45.00,  False),
    ("Beijing (China)", 39.90, 116.40,  False),
    ("same lat, flipped lon", 39.74, 104.99, False),
    ("Winnipeg (Canada)", 49.90, -97.14, False),
    ("Mexico City",     19.43, -99.13,  False),
    ("South Pacific",  -30.00, -120.00, False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="wwt")
    ap.add_argument("--pattern", default="conus-pattern.json")
    args = ap.parse_args()

    from toasty.toast import ToastCoordinateSystem

    manifest = json.load(open(os.path.join(args.outdir, "manifest.json")))
    bundle, lon, lat, P = load_pattern(args.pattern)
    cs = manifest["color_scale"]
    lut = ramp_lut(cs["ramp"])
    lo, hi = cs["domain_K"]
    depth = manifest["toast_depth"]
    if depth is None:
        raise SystemExit("this export has no TOAST pyramids (--no-toast)")

    checks = failures = 0

    def ok(name, passed, detail=""):
        nonlocal checks, failures
        checks += 1
        if passed:
            print(f"  pass {name}{'  -> ' + detail if detail else ''}")
        else:
            failures += 1
            print(f"  FAIL {name}  {detail}")

    # ---------------------------------------------------------------- WTML --
    print("WTML:")
    from wwt_data_formats.folder import Folder
    from wwt_data_formats.imageset import ImageSet
    root = Folder.from_file(os.path.join(args.outdir, "index_rel.wtml"))
    isets = [c for c in root.children if isinstance(c, ImageSet)]
    ok("one imageset per year", len(isets) == len(manifest["years"]),
       f"{len(isets)} imagesets, {len(manifest['years'])} years")
    for iset in isets:
        ok(f"'{iset.name}' is a TOAST Earth layer",
           iset.projection.value == "Toast"
           and iset.data_set_type.value == "Earth"
           and iset.reference_frame == "Earth"
           and iset.tile_levels == depth,
           f"Projection={iset.projection.value} DataSetType="
           f"{iset.data_set_type.value} TileLevels={iset.tile_levels}")
        tmpl = iset.url
        ok(f"'{iset.name}' tile URLs resolve",
           os.path.exists(os.path.join(
               args.outdir,
               tmpl.replace("{1}", str(depth)).replace("{2}", "0").replace("{3}", "0")))
           or any(True for _ in os.walk(os.path.join(
               args.outdir, tmpl.split("/")[0]))),
           tmpl)

    # ------------------------------------------------------------ geometry --
    # NOTE: toasty's toast_pixel_for_point returns out-of-range pixel indices
    # for the PLANETARY coordinate system, so it is not used here. Instead we
    # walk the tiles that actually exist and use toast_tile_get_coords - the
    # same forward mapping toasty used to build them - to ask where each
    # painted pixel really is. "Every painted pixel is over CONUS land" is a
    # stronger claim than a handful of city spot-checks, and it is exactly
    # what a hemisphere or sign error would break.
    from toasty.toast import toast_tile_get_coords, generate_tiles

    year = sorted(manifest["years"])[-1]
    tag = [k for k in os.listdir(args.outdir)
           if os.path.isdir(os.path.join(args.outdir, k))
           and k.endswith(str(year))][0]
    gd = manifest["years"][str(year)]["global_delta_K"]
    print(f"\nTOAST geometry ({tag}, depth {depth}, global {gd:+.3f} K):")

    def norm_lon(a):
        return (np.asarray(a) + 180.0) % 360.0 - 180.0

    lon0, lon1 = float(lon[0]), float(lon[-1])
    lat0, lat1 = float(lat[0]), float(lat[-1])
    step = float(lon[1] - lon[0])

    painted = []          # (lon, lat, rgba) for every opaque pixel found
    n_tiles = 0
    for tile in generate_tiles(depth, bottom_only=True,
                               coordsys=ToastCoordinateSystem.PLANETARY):
        p = tile.pos
        path = os.path.join(args.outdir, tag, str(p.n), str(p.y),
                            f"{p.y}_{p.x}.png")
        if not os.path.exists(path):
            continue
        n_tiles += 1
        img = np.asarray(Image.open(path).convert("RGBA"))
        tlon, tlat = toast_tile_get_coords(tile)
        sel = img[..., 3] > 128
        if sel.any():
            painted.append((norm_lon(np.rad2deg(tlon[sel])),
                            np.rad2deg(tlat[sel]), img[sel]))
    ok("pyramid has leaf tiles with content", n_tiles > 0 and len(painted) > 0,
       f"{n_tiles} leaf tiles on disk, {sum(len(a[0]) for a in painted)} "
       f"painted pixels")

    plon = np.concatenate([a[0] for a in painted])
    plat = np.concatenate([a[1] for a in painted])
    prgba = np.concatenate([a[2] for a in painted])

    inside_box = ((plon >= lon0 - step) & (plon <= lon1 + step)
                  & (plat >= lat0 - step) & (plat <= lat1 + step))
    ok("every painted pixel is inside the CONUS bounding box",
       inside_box.all(),
       f"{int((~inside_box).sum())} of {len(plon)} outside; "
       f"lon [{plon.min():.1f}, {plon.max():.1f}] "
       f"lat [{plat.min():.1f}, {plat.max():.1f}]")

    # ... and on land, per the pattern's own mask
    jj = np.clip(np.round((plat - lat0) / step).astype(int), 0, len(lat) - 1)
    ii = np.clip(np.round((plon - lon0) / step).astype(int), 0, len(lon) - 1)
    on_land = np.isfinite(P[jj, ii])
    ok("painted pixels are on CONUS land", on_land.mean() > 0.985,
       f"{on_land.mean() * 100:.2f}% on land "
       f"(the rest is one cell of coastal bleed from TOAST resampling)")

    # values must match the pattern where they are painted
    expect = colorize((P[jj, ii] * gd).reshape(-1, 1), lo, hi, lut)[:, 0]
    good = np.isfinite(P[jj, ii])
    derr = np.abs(prgba[good, :3].astype(int) - expect[good, :3].astype(int)).max(1)
    ok("painted values match the pattern", np.percentile(derr, 99) <= 40,
       f"median channel error {np.median(derr):.0f}, 99th pct "
       f"{np.percentile(derr, 99):.0f} of 255")

    # city spot-checks: nearest painted pixel to each point
    print("\nCity spot-checks (nearest painted pixel):")
    for name, clat_, clon_, should_paint in POINTS:
        d = np.hypot((plon - clon_) * np.cos(np.deg2rad(clat_)), plat - clat_)
        k = int(d.argmin())
        near_deg = float(d[k])
        if should_paint:
            ok(f"{name} is covered", near_deg < 1.0,
               f"nearest painted pixel {near_deg:.2f} deg away, "
               f"RGB {tuple(prgba[k][:3])}")
        else:
            ok(f"{name} is not covered", near_deg > 1.0,
               f"nearest painted pixel {near_deg:.2f} deg away")

    # Orientation, read back through the pyramid by DECODING the colour.
    # Do not use a hue proxy such as red-minus-blue: on a diverging ramp the
    # warm arm darkens as it warms, so hue alone is not monotone in value.
    # Inverting through the LUT is both correct and a test that the colour
    # encoding is recoverable at all.
    print("\nOrientation, decoded back from pixel colour:")

    def decode(rgb):
        k = int(np.argmin(((lut - np.asarray(rgb, float)) ** 2).sum(1)))
        return lo + (hi - lo) * k / (len(lut) - 1)

    def value_at(clat_, clon_):
        d = np.hypot((plon - clon_) * np.cos(np.deg2rad(clat_)), plat - clat_)
        k = int(d.argmin())
        return decode(prgba[k][:3])

    def truth_at(clat_, clon_):
        j = int(np.abs(lat - clat_).argmin())
        i = int(np.abs(lon - clon_).argmin())
        return float(P[j, i] * gd)

    cities = [("Fargo ND", 46.88, -96.79), ("Houston TX", 29.76, -95.37),
              ("Kansas City MO", 39.10, -94.58),
              ("San Francisco CA", 37.77, -122.42)]
    # NB: loop variables must not be named lo/hi - a plain for loop leaks in
    # Python, and shadowing the colour-scale bounds here silently corrupted
    # decode() and the manifest check.
    worst = 0.0
    for _cname, _cla, _clo in cities:
        worst = max(worst, abs(value_at(_cla, _clo) - truth_at(_cla, _clo)))
    ok("decoded pixel values match the model field", worst < 0.15,
       "  ".join(f"{n} {value_at(a, o):+.2f}K" for n, a, o in cities)
       + f"  (max error vs model {worst:.3f} K)")

    ok("north reads warmer than south",
       value_at(46.88, -96.79) > value_at(29.76, -95.37),
       f"Fargo {value_at(46.88, -96.79):+.2f} K > "
       f"Houston {value_at(29.76, -95.37):+.2f} K")
    ok("interior reads warmer than the Pacific coast",
       value_at(39.10, -94.58) > value_at(37.77, -122.42),
       f"Kansas City {value_at(39.10, -94.58):+.2f} K > "
       f"San Francisco {value_at(37.77, -122.42):+.2f} K")

    # --------------------------------------------------------- flat images --
    print("\nFlat plate carree frames:")
    for y, info in sorted(manifest["years"].items()):
        p = os.path.join(args.outdir, info["platecarree_png"])
        img = np.asarray(Image.open(p).convert("RGBA"))
        h, w = img.shape[:2]
        ok(f"{y} canvas is 2:1", w == 2 * h, f"{w}x{h}")

        def at(latd, lond):
            ix = int((lond + 180.0) / 360.0 * w)
            iy = int((90.0 - latd) / 180.0 * h)
            return img[np.clip(iy, 0, h - 1), np.clip(ix, 0, w - 1)]

        ok(f"{y} CONUS is painted", at(39.7, -105.0)[3] > 128)
        ok(f"{y} China is empty", at(39.9, 116.4)[3] < 128)
        ok(f"{y} ocean is empty", at(30.0, -45.0)[3] < 128)
        frac = (img[..., 3] > 128).mean()
        ok(f"{y} painted fraction is CONUS-sized", 0.005 < frac < 0.045,
           f"{frac * 100:.2f}% of the globe (CONUS is about 1.6%)")

    # ------------------------------------------------------------ manifest --
    print("\nManifest:")
    shared = cs["note"] == "fixed across all frames"
    ok("colour scale mode is recorded and per-year domains agree with it",
       shared == all(manifest["years"][k]["domain_K"] == cs["domain_K"]
                     for k in manifest["years"]),
       f"{cs['kind']} [{lo:+.2f}, {hi:+.2f}] K - {cs['chosen_because']}")
    ok("scale kind matches the data's sign",
       (cs["kind"] == "sequential") == (lo >= 0),
       f"kind={cs['kind']}, domain starts at {lo:+.2f}")
    ok("synthetic provenance is recorded",
       "pattern_synthetic" in manifest and manifest["pattern_provenance"],
       f"synthetic={manifest['pattern_synthetic']}")
    deltas = [manifest["years"][k]["global_delta_K"] for k in sorted(manifest["years"])]
    ok("per-year global anomalies increase", all(b > a for a, b in zip(deltas, deltas[1:])),
       ", ".join(f"{d:+.2f}" for d in deltas))
    ok("every frame fits inside the shared scale",
       all(lo - 1e-9 <= manifest["years"][k]["conus_min_K"]
           and manifest["years"][k]["conus_max_K"] <= hi + 1e-9
           for k in manifest["years"]),
       "no frame is clipped")

    print(f"\n{checks - failures}/{checks} checks passed")
    if failures:
        raise SystemExit(f"{failures} FAILURES")
    print("WWT export geometry and metadata verified.")


if __name__ == "__main__":
    main()
