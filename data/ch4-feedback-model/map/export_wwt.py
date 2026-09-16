#!/usr/bin/env python3
"""
export_wwt.py - render the pattern-scaled warming maps as image sets for
WorldWide Telescope (and, as a bonus, for any other globe viewer).

    pip install toasty --no-deps          # pims, its video loader dep, won't build
    pip install wwt_data_formats pillow pyyaml numpy scipy matplotlib
    python3 export_wwt.py --scenario ssp245 --years 2030,2050,2075,2100

Outputs, under --outdir (default "wwt"):

    index_rel.wtml              WWT folder listing every year - open this in WWT
    <scenario>_<year>/          one TOAST tile pyramid per year, plus its own WTML
    platecarree/*.png           global plate carree frames (2:1), transparent
                                outside CONUS - for Cesium, three.js, Blender...
    platecarree/*.kml           Google Earth GroundOverlay per year
    conus_crop/*.png + .pgw     tight CONUS crops with ESRI world files (GIS)
    legend.png                  the colour bar
    manifest.json               colour scale, per-year global dT, provenance

WHY TOAST
---------
WWT displays full-sphere imagery as a TOAST (Tessellated Octahedral Adaptive
Subdivision Transform) tile pyramid. Rather than guess at a partial-coverage
projection, this embeds the CONUS field in a full-globe plate carree canvas
that is transparent everywhere else, and lets toasty resample it to TOAST. The
geometry is then exactly right and the layer only paints over CONUS, so WWT's
own basemap shows through elsewhere.

THE COLOUR SCALE IS FIXED ACROSS ALL YEARS
------------------------------------------
Computed once from the full set of requested years, then reused for every
frame. Per-frame autoscaling is the classic way to make an animation
meaningless - everything looks equally red in every year.

The pattern is SYNTHETIC unless you have run derive_pattern_from_cmip6.py; the
manifest and the WTML credits say which.
"""

import argparse
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "bundle"))


# --------------------------------------------------------------------------- #
# Field construction (mirrors ch4map.js)
# --------------------------------------------------------------------------- #

def load_pattern(path="conus-pattern.json"):
    b = json.load(open(path))
    g = b["meta"]["grid"]
    lon = np.asarray(b["lon"], float)
    lat = np.asarray(b["lat"], float)
    P = np.asarray(b["pattern"], float).reshape(g["nlat"], g["nlon"])
    P = np.where(P == b["meta"]["nodata"], np.nan, P)
    return b, lon, lat, P


def global_series(scenario, gamma, start=1750, end=2100):
    """dT_global(t) from the Python reference implementation."""
    import ch4feedback as cf
    scen = cf.build_scenario(scenario, cache_dir=os.path.join("..", "bundle", "data"))
    params, _ = cf.calibrate(
        {k: cf.build_scenario(k, cache_dir=os.path.join("..", "bundle", "data"))
         for k in ["ssp126", "ssp245", "ssp370", "ssp585"]},
        fit=("tau_base", "e_nat"), start_year=1850, end_year=2100)
    params = params.replace(gamma_wetland=gamma)
    r = cf.run(scen, params, start, end)
    return r["year"], r["temperature"], params


def rebase(year, temp, baseline):
    m = (year >= baseline[0]) & (year <= baseline[1])
    if not m.any():
        raise SystemExit(f"baseline {baseline} outside {year[0]:.0f}-{year[-1]:.0f}")
    return temp - temp[m].mean()


def nan_fill_nearest(A):
    """Nearest-neighbour extrapolation into the NaNs.

    Needed before bilinear upsampling: plain bilinear against NaN erodes the
    coastline by a cell. Values are filled, then the ORIGINAL mask is reapplied
    with nearest-neighbour, so interiors stay smooth and coasts stay crisp.
    """
    from scipy.ndimage import distance_transform_edt
    bad = ~np.isfinite(A)
    if not bad.any():
        return A
    idx = distance_transform_edt(bad, return_distances=False, return_indices=True)
    return A[tuple(idx)]


def to_global_canvas(field, lon, lat, width):
    """Embed the CONUS field in a global plate carree canvas.

    Returns (values, mask). data[0,0] is lon=-180, lat=+90: toasty's
    plate_carree_planet_sampler convention, verified empirically.
    """
    from scipy.interpolate import RegularGridInterpolator
    height = width // 2
    step = 360.0 / width
    clon = -180.0 + (np.arange(width) + 0.5) * step
    clat = 90.0 - (np.arange(height) + 0.5) * step

    filled = nan_fill_nearest(field)
    mask = np.isfinite(field).astype(float)
    dlon = lon[1] - lon[0]
    src_lon = np.concatenate([[lon[0] - dlon], lon, [lon[-1] + dlon]])
    src_lat = np.concatenate([[lat[0] - dlon], lat, [lat[-1] + dlon]])

    def pad(A, edge):
        A = np.pad(A, 1, mode="edge") if edge else np.pad(A, 1, constant_values=0.0)
        return A

    fv = RegularGridInterpolator((src_lat, src_lon), pad(filled, True),
                                 method="linear", bounds_error=False, fill_value=np.nan)
    fm = RegularGridInterpolator((src_lat, src_lon), pad(mask, False),
                                 method="nearest", bounds_error=False, fill_value=0.0)

    sub_j = np.flatnonzero((clat >= lat[0] - dlon) & (clat <= lat[-1] + dlon))
    sub_i = np.flatnonzero((clon >= lon[0] - dlon) & (clon <= lon[-1] + dlon))
    out = np.full((height, width), np.nan)
    if len(sub_j) and len(sub_i):
        LA, LO = np.meshgrid(clat[sub_j], clon[sub_i], indexing="ij")
        pts = np.stack([LA.ravel(), LO.ravel()], -1)
        v = fv(pts).reshape(LA.shape)
        m = fm(pts).reshape(LA.shape)
        out[np.ix_(sub_j, sub_i)] = np.where(m > 0.5, v, np.nan)
    return out


# --------------------------------------------------------------------------- #
# Colour
# --------------------------------------------------------------------------- #

def ramp_lut(ramp_hex, n=512):
    stops = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in ramp_hex],
                     float)
    x = np.linspace(0, len(stops) - 1, n)
    lo = np.clip(np.floor(x).astype(int), 0, len(stops) - 2)
    fr = (x - lo)[:, None]
    return stops[lo] * (1 - fr) + stops[lo + 1] * fr


def choose_scale(fields):
    """Pick the encoding from the data, not by habit.

    A field that never crosses zero is a MAGNITUDE and takes a sequential
    ramp over [0, max]; a diverging scale there would spend half its range on
    values that never occur and visibly flatten the spatial structure. A field
    that does cross zero - an overshoot scenario, or early years against a
    present-day baseline - is a POLARITY and takes a symmetric diverging
    scale, so the midpoint keeps meaning "no change".

    Returns (kind, lo, hi).
    """
    lo = min(float(np.nanmin(f)) for f in fields)
    hi = max(float(np.nanmax(f)) for f in fields)
    span = max(abs(lo), abs(hi))
    if lo < -0.05 * span:                       # meaningfully two-sided
        h = float(np.ceil(span * 20) / 20)
        return "diverging", -h, h
    return "sequential", 0.0, float(np.ceil(hi * 20) / 20)


def colorize(values, lo, hi, lut):
    """-> RGBA uint8 over the domain [lo, hi]. NaN becomes fully transparent."""
    h, w = values.shape
    out = np.zeros((h, w, 4), np.uint8)
    good = np.isfinite(values)
    t = np.clip((values[good] - lo) / (hi - lo), 0, 1)
    idx = np.round(t * (len(lut) - 1)).astype(int)
    out[good, :3] = lut[idx].astype(np.uint8)
    out[good, 3] = 255
    return out


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #

def write_png(rgba, path):
    from PIL import Image
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def write_kml(path, name, png_name, bbox, description=""):
    w, s, e, n = bbox
    open(path, "w").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <GroundOverlay>
    <name>{name}</name>
    <description>{description}</description>
    <Icon><href>{png_name}</href></Icon>
    <LatLonBox>
      <north>{n}</north><south>{s}</south><east>{e}</east><west>{w}</west>
    </LatLonBox>
  </GroundOverlay>
</kml>
""")


def write_worldfile(path, bbox, width, height):
    """ESRI world file: pixel size, rotation, and the CENTRE of the top-left px."""
    w, s, e, n = bbox
    px = (e - w) / width
    py = (n - s) / height
    open(path, "w").write(
        f"{px:.10f}\n0.0000000000\n0.0000000000\n{-py:.10f}\n"
        f"{w + px / 2:.10f}\n{n - py / 2:.10f}\n")


def write_legend(path, lo, hi, lut, label):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    fig, ax = plt.subplots(figsize=(6.4, 0.95))
    cmap = ListedColormap(lut / 255.0)
    grad = np.linspace(lo, hi, 512)[None, :]
    ax.imshow(grad, aspect="auto", cmap=cmap, extent=[lo, hi, 0, 1],
              vmin=lo, vmax=hi)
    ax.set_yticks([])
    ax.set_xlabel(label, fontsize=9)
    ax.tick_params(labelsize=8)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140, transparent=True)
    plt.close(fig)


def make_tile_filter(bbox, pad_deg=5.0, min_depth=3):
    """Prune TOAST subtrees that cannot touch the region.

    Without this, toasty samples all 4**depth leaf tiles to discover that
    almost all of them are empty - 67 million sampler calls at depth 5 for a
    region covering 1.6% of the globe.

    Conservative by construction: tiles shallower than ``min_depth`` are always
    accepted, because low-depth TOAST tiles are big octahedral triangles whose
    corner list does not bound them usefully (one corner sits on a pole and the
    longitudes wrap). A tile spanning more than 180 degrees of longitude is
    also always accepted. Over-accepting only costs time; under-accepting would
    silently drop data, which is why validate_wwt.py checks coverage.
    """
    w, s, e, n = bbox

    def f(tile):
        if tile.pos.n < min_depth:
            return True
        lons = np.asarray([np.rad2deg(c[0]) for c in tile.corners], float)
        lats = np.asarray([np.rad2deg(c[1]) for c in tile.corners], float)
        lons = (lons + 180.0) % 360.0 - 180.0
        if lats.max() < s - pad_deg or lats.min() > n + pad_deg:
            return False
        if lons.max() - lons.min() > 180.0:
            return True                      # wraps: cannot bound cheaply
        if lons.max() < w - pad_deg or lons.min() > e + pad_deg:
            return False
        return True

    return f


def build_toast(values, lo, hi, lut, outdir, name, depth, credits,
                is_synthetic, tile_filter=None):
    """One TOAST pyramid + its WTML. Returns the relative WTML path."""
    from toasty.builder import Builder
    from toasty.pyramid import PyramidIO
    from toasty.samplers import plate_carree_planet_sampler
    from wwt_data_formats.enums import DataSetType

    rgba = colorize(values, lo, hi, lut)
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    pio = PyramidIO(outdir, default_format="png")
    builder = Builder(pio)
    kw = {"tile_filter": tile_filter} if tile_filter else {}
    builder.toast_base(plate_carree_planet_sampler(rgba), depth,
                       is_planet=True, **kw)
    builder.cascade()

    imgset = builder.imgset
    imgset.name = name
    imgset.data_set_type = DataSetType.EARTH      # an Earth layer, not a planet
    imgset.reference_frame = "Earth"
    imgset.credits = credits
    imgset.credits_url = ""
    imgset.file_type = ".png"
    builder.place.name = name
    builder.place.zoom_level = 8.0
    # wwt_data_formats Place uses latitude/longitude for Earth frames
    builder.place.longitude = -98.5                # centre on CONUS
    builder.place.latitude = 39.5
    builder.place.data_set_type = DataSetType.EARTH
    builder.make_placeholder_thumbnail()
    builder.write_index_rel_wtml()
    return os.path.join(outdir, "index_rel.wtml")


def combined_wtml(path, folder_name, entries, base_url=""):
    """One WTML folder holding every year, so WWT shows them as a set."""
    from wwt_data_formats.folder import Folder
    from wwt_data_formats.imageset import ImageSet
    from wwt_data_formats import write_xml_doc

    root = Folder()
    root.name = folder_name
    root.group = "Explorer"
    for sub_wtml, label, prefix in entries:
        f = Folder.from_file(sub_wtml)
        # the per-year WTML has URLs relative to its own directory; re-root
        # them at the combined file's directory
        f.mutate_urls(lambda u, p=prefix: (
            p + "/" + u if u and not u.startswith(("http://", "https://")) else u))
        for child in f.children:
            child.name = label
            root.children.append(child)
    if base_url:
        root.mutate_urls(lambda u: (
            base_url.rstrip("/") + "/" + u
            if u and not u.startswith(("http://", "https://")) else u))
    with open(path, "wt", encoding="utf8") as f:
        write_xml_doc(root.to_xml(), dest_stream=f)


# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="ssp245")
    ap.add_argument("--years", default="2030,2050,2075,2100",
                    help="comma-separated, or START:END:STEP")
    ap.add_argument("--gamma", type=float, default=20.0,
                    help="gamma_wetland [Tg CH4/yr/K]")
    ap.add_argument("--baseline", nargs=2, type=int, default=(1995, 2014),
                    metavar=("Y0", "Y1"))
    ap.add_argument("--loop-only", action="store_true",
                    help="map the methane loop's OWN contribution "
                         "(with minus without feedback) instead of total warming")
    ap.add_argument("--depth", type=int, default=5,
                    help="TOAST depth; 5 is about 0.04 deg/px, plenty for "
                         "0.5 deg source data")
    ap.add_argument("--canvas-width", type=int, default=4096,
                    help="global plate carree width (height is half)")
    ap.add_argument("--pattern", default="conus-pattern.json")
    ap.add_argument("--outdir", default="wwt")
    ap.add_argument("--base-url", default="",
                    help="prefix for absolute URLs in index.wtml, if you will "
                         "serve the tiles over HTTP")
    ap.add_argument("--scale-mode", choices=("shared", "per-frame"),
                    default="shared",
                    help="shared (default): one colour scale for every frame, "
                         "so years are comparable and the animation means "
                         "something - but within-year spatial structure looks "
                         "flat, because it is small next to the total warming. "
                         "per-frame: rescale each year to its own range, which "
                         "shows the spatial pattern but makes every year look "
                         "equally warm. Pick by the question you are asking.")
    ap.add_argument("--no-toast", action="store_true",
                    help="skip the TOAST pyramids; only write the flat images")
    args = ap.parse_args()

    if ":" in args.years:
        a, b, c = (int(x) for x in args.years.split(":"))
        years = list(range(a, b + 1, c))
    else:
        years = [int(y) for y in args.years.split(",")]

    bundle, lon, lat, P = load_pattern(args.pattern)
    synthetic = bool(bundle["meta"].get("synthetic"))
    print(f"pattern: {'SYNTHETIC' if synthetic else 'CMIP6-derived'}, "
          f"{len(lon)}x{len(lat)} grid")

    print(f"running the coupled model: {args.scenario}, gamma={args.gamma}")
    yr, temp, params = global_series(args.scenario, args.gamma)
    if args.loop_only:
        _, temp0, _ = global_series(args.scenario, 0.0)
        delta = temp - temp0            # already a difference: no rebasing
        label_kind = "methane-loop contribution to warming"
        baseline_txt = "with minus without feedback"
    else:
        delta = rebase(yr, temp, args.baseline)
        label_kind = f"warming vs {args.baseline[0]}-{args.baseline[1]}"
        baseline_txt = f"{args.baseline[0]}-{args.baseline[1]}"

    gd = {}
    for y in years:
        i = int(np.abs(yr - y).argmin())
        if abs(yr[i] - y) > 0.5:
            raise SystemExit(f"year {y} not in the run")
        gd[y] = float(delta[i])

    # ---- ONE colour scale for every frame -------------------------------
    fields = {y: P * gd[y] for y in years}
    per_frame = args.scale_mode == "per-frame"
    scales = {}
    if per_frame:
        for y in years:
            scales[y] = choose_scale([fields[y]])
        kind = scales[years[0]][0]
        lo = min(s[1] for s in scales.values())
        hi = max(s[2] for s in scales.values())
        print(f"PER-FRAME colour scales ({kind}): each year rescaled to its "
              f"own range. Years are NOT comparable with each other.")
        for y in years:
            print(f"  {y}: [{scales[y][1]:+.2f}, {scales[y][2]:+.2f}] K")
    else:
        kind, lo, hi = choose_scale(list(fields.values()))
        for y in years:
            scales[y] = (kind, lo, hi)
        print(f"shared colour scale: {kind}, [{lo:+.2f}, {hi:+.2f}] K, fixed "
              f"across all {len(years)} frames so the animation is comparable")
        if kind == "sequential":
            print("  (the field never goes negative, so a diverging scale "
                  "would waste half its range and flatten the pattern)")
        print("  note: within-year spatial structure will look flat, because "
              "it is small next to the total warming. --scale-mode per-frame "
              "shows the pattern instead, at the cost of comparability.")
    ramp_hex = bundle["ramp"]["sequential" if kind == "sequential" else "diverging"]
    lut = ramp_lut(ramp_hex)

    os.makedirs(args.outdir, exist_ok=True)
    label_unit = f"{label_kind} [K]"
    write_legend(os.path.join(args.outdir, "legend.png"), lo, hi, lut, label_unit)

    credits = ("Pattern-scaled from a coupled CH4-temperature box model. "
               + ("PATTERN IS SYNTHETIC - not derived from CMIP6."
                  if synthetic else "Pattern derived from CMIP6 tas."))

    bbox_conus = [float(lon[0]), float(lat[0]),
                  float(lon[-1]), float(lat[-1])]
    entries, manifest_years = [], {}

    for y in years:
        tag = f"{args.scenario}_{'loop_' if args.loop_only else ''}{y}"
        print(f"\n{y}: global {gd[y]:+.3f} K, "
              f"CONUS {np.nanmean(fields[y]):+.3f} K")

        canvas = to_global_canvas(fields[y], lon, lat, args.canvas_width)
        _, ylo, yhi = scales[y]
        rgba = colorize(canvas, ylo, yhi, lut)
        pc_png = os.path.join(args.outdir, "platecarree", f"{tag}.png")
        write_png(rgba, pc_png)
        write_kml(os.path.join(args.outdir, "platecarree", f"{tag}.kml"),
                  f"{tag} ({label_kind})", f"{tag}.png",
                  [-180.0, -90.0, 180.0, 90.0],
                  f"global dT {gd[y]:+.3f} K; scale [{ylo:+.2f},{yhi:+.2f}] K")

        # tight CONUS crop + world file, for GIS and for lighter web overlays
        crop_rgba = colorize(fields[y][::-1, :], ylo, yhi, lut)  # north-up
        crop_png = os.path.join(args.outdir, "conus_crop", f"{tag}.png")
        write_png(crop_rgba, crop_png)
        step = float(lon[1] - lon[0])
        write_worldfile(os.path.join(args.outdir, "conus_crop", f"{tag}.pgw"),
                        [bbox_conus[0] - step / 2, bbox_conus[1] - step / 2,
                         bbox_conus[2] + step / 2, bbox_conus[3] + step / 2],
                        len(lon), len(lat))
        write_kml(os.path.join(args.outdir, "conus_crop", f"{tag}.kml"),
                  f"{tag} CONUS", f"{tag}.png",
                  [bbox_conus[0] - step / 2, bbox_conus[1] - step / 2,
                   bbox_conus[2] + step / 2, bbox_conus[3] + step / 2])

        if not args.no_toast:
            sub = os.path.join(args.outdir, tag)
            wtml = build_toast(
                canvas, ylo, yhi, lut, sub,
                f"{args.scenario.upper()} {y} - {label_kind}",
                args.depth, credits, synthetic,
                tile_filter=make_tile_filter(bbox_conus))
            entries.append((wtml, f"{args.scenario.upper()} {y}", tag))
            n_tiles = sum(len(fs) for _, _, fs in os.walk(sub)
                          if True)
            print(f"  TOAST depth {args.depth}: {n_tiles} files in {sub}/")

        manifest_years[y] = {
            "global_delta_K": round(gd[y], 4),
            "conus_mean_K": round(float(np.nanmean(fields[y])), 4),
            "conus_min_K": round(float(np.nanmin(fields[y])), 4),
            "conus_max_K": round(float(np.nanmax(fields[y])), 4),
            "domain_K": [scales[y][1], scales[y][2]],
            "platecarree_png": os.path.relpath(pc_png, args.outdir),
            "conus_crop_png": os.path.relpath(crop_png, args.outdir),
        }

    if entries:
        combined = os.path.join(args.outdir, "index_rel.wtml")
        combined_wtml(combined, f"CH4 feedback - {args.scenario.upper()}",
                      entries)
        print(f"\nwrote {combined}  <- open this in WorldWide Telescope")
        if args.base_url:
            abs_path = os.path.join(args.outdir, "index.wtml")
            combined_wtml(abs_path, f"CH4 feedback - {args.scenario.upper()}",
                          entries, base_url=args.base_url)
            print(f"wrote {abs_path}  (absolute URLs under {args.base_url})")

    manifest = {
        "scenario": args.scenario,
        "field": "loop_contribution" if args.loop_only else "warming_vs_baseline",
        "baseline": baseline_txt,
        "label": label_unit,
        "color_scale": {"kind": kind, "domain_K": [lo, hi],
                        "symmetric": kind == "diverging",
                        "ramp": ramp_hex,
                        "note": ("per frame - years are NOT comparable"
                                 if per_frame else "fixed across all frames"),
                        "chosen_because": (
                            "the field never crosses zero, so magnitude "
                            "(sequential) is the right encoding"
                            if kind == "sequential" else
                            "the field crosses zero, so polarity "
                            "(diverging, symmetric) is the right encoding")},
        "gamma_wetland": args.gamma,
        "model_params": {k: (round(v, 6) if isinstance(v, float) else v)
                         for k, v in vars(params).items()},
        "pattern_synthetic": synthetic,
        "pattern_provenance": bundle["meta"].get("warning"),
        "conus_bbox_lonlat": bbox_conus,
        "toast_depth": None if args.no_toast else args.depth,
        "canvas": {"width": args.canvas_width, "height": args.canvas_width // 2,
                   "projection": "plate carree, lon -180 at left, lat +90 at top"},
        "years": manifest_years,
    }
    json.dump(manifest, open(os.path.join(args.outdir, "manifest.json"), "w"),
              indent=1)
    print(f"wrote {os.path.join(args.outdir, 'manifest.json')}")


if __name__ == "__main__":
    main()
