/**
 * The globe that runs inside each iframe.
 *
 * Deliberately not a Vue app. Using WWTInstance directly rather than
 * engine-pinia's <WorldWideTelescope> buys three things:
 *
 *  - `startMode: "earth"` boots straight into Earth mode, so the engine builds
 *    its own Blue Marble imageset and public/earth.wtml is not needed here.
 *  - `ctl` is public, so the zoom-out limit can be raised. The default caps the
 *    viewport at 60 degrees, which is not enough to frame the whole disk in a
 *    tall narrow panel.
 *  - no Vue, pinia or Vuetify in this bundle.
 *
 * One realm per iframe is the whole point: the engine keeps its control object
 * in a module-level global, so two globes cannot share a realm.
 */
import { WWTInstance } from "@wwtelescope/engine-helpers";

/** Where the GCReW marsh is: Smithsonian Environmental Research Center, MD. */
const GCREW_LAT = 38.8748;
const GCREW_LON = -76.5457;

function numberParam(name: string, fallback: number): number {
  const raw = new URLSearchParams(window.location.search).get(name);
  const value = raw === null ? NaN : Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

const latDeg = numberParam("lat", GCREW_LAT);
const lonDeg = numberParam("lon", GCREW_LON);
const zoomDeg = numberParam("zoom", 120);

/**
 * Optional temperature map to drape over Blue Marble, named as it appears in
 * public/tempmaps/index_rel.wtml, e.g. "SSP245 2100". Fixed per globe, so it
 * rides in the query string without ever forcing a reload.
 */
const layerName = new URLSearchParams(window.location.search).get("layer");
const layerOpacity = numberParam("opacity", 0.75);

const wwt = new WWTInstance({
  elId: "earth-mount",
  startInternalRenderLoop: true,
  // The string rather than InitControlViewType.Earth: that is a `const enum`,
  // and esbuild transpiles each file on its own, so importing one does not
  // survive the build.
  startMode: "earth" as never,
  startLatDeg: latDeg,
  startLngDeg: lonDeg,
  startZoomDeg: zoomDeg,
});

/** Points the camera at the marsh. Swapping the background can reset it. */
function reaim() {
  wwt.gotoRADecZoom(
    // Earth mode reads the camera as (lon, lat) but still takes it through the
    // RA argument, and the engine negates on the way through, so the longitude
    // goes in with its sign flipped.
    (-lonDeg * Math.PI) / 180,
    (latDeg * Math.PI) / 180,
    zoomDeg,
    true,
  );
}

/** Loaded once; swapping layers afterwards is just a background change. */
let collectionLoaded = false;

/**
 * Loads the temperature-map collection, rewriting its tile paths first.
 *
 * The shipped WTML uses paths relative to itself, and the engine resolves them
 * against the *page* instead, so the tiles are looked up one directory too high.
 * Hardcoding a leading "/tempmaps/" fixed that locally and broke the deployed
 * build, where the site lives under a repository subpath and the tiles 404.
 *
 * So the paths are made fully qualified here, against wherever the WTML
 * actually is, and the patched document is handed to the engine as a blob. That
 * works under any base, which is what `base: "./"` in vite.config.mts requires.
 *
 * Prefixed by string rather than through `new URL()` on purpose: the tile paths
 * are templates like `{1}/{3}/{3}_{2}.png`, and URL encoding would turn the
 * braces into %7B and %7D and break the substitution.
 */
async function loadCollection() {
  const wtmlUrl = new URL("tempmaps/index_rel.wtml", document.baseURI).href;
  const directory = wtmlUrl.replace(/[^/]*$/, "");

  const absolute = (path: string) =>
    /^(https?:)?\/\//.test(path) || path.startsWith("/") ? path : directory + path;

  const patched = (await (await fetch(wtmlUrl)).text())
    .replace(/(Url|ThumbnailUrl)="([^"]*)"/g, (_m, attr, path) => `${attr}="${absolute(path)}"`)
    .replace(/<ThumbnailUrl>([^<]*)<\/ThumbnailUrl>/g,
      (_m, path) => `<ThumbnailUrl>${absolute(path)}</ThumbnailUrl>`);

  const blobUrl = URL.createObjectURL(new Blob([patched], { type: "application/xml" }));
  try {
    // No child folders in this document, so do not let the engine chase any
    // against a blob URL that has no directory to resolve against.
    await wwt.loadImageCollection(blobUrl, false);
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

/**
 * The globe the engine built for us at startup, kept so it can be put back.
 *
 * Restoring by name does not work: `startMode: "earth"` constructs the Blue
 * Marble imageset and hands it straight to the render context without adding it
 * to the named repository, so `setBackgroundImageByName("Blue Marble")` finds
 * nothing and returns quietly. Holding the object is the reliable route.
 */
let bareGlobe: ReturnType<typeof wwt.ctl.renderContext.get_backgroundImageset> = null;

/** Shows a temperature map, or restores the bare globe when given "". */
async function applyLayer(name: string) {
  if (!name) {
    if (bareGlobe) {
      wwt.ctl.renderContext.set_backgroundImageset(bareGlobe);
      wwt.ctl.renderContext.set_foregroundImageset(bareGlobe);
      reaim();
    }
    return;
  }
  if (!collectionLoaded) {
    await loadCollection();
    collectionLoaded = true;
  }

  /* Set as the background, not the foreground. The engine reads its render mode
     off the background imageset, and these maps are DataSetType="Earth", so
     they render directly. Draping them as a foreground over Blue Marble left
     the globe unchanged with no error, and there was no time to chase why
     before the report-out. Blue Marble is therefore replaced rather than
     tinted, which for a temperature map is arguably the clearer picture. */
  wwt.setBackgroundImageByName(name);
  wwt.setForegroundImageByName(name);
  wwt.setForegroundOpacity(layerOpacity * 100);
  reaim();
}

wwt.waitForReady().then(() => {
  // Zoom is stored as viewport degrees times six, and the default ceiling of
  // 360 means 60 degrees. Raising it lets a tall panel pull back far enough to
  // hold the whole globe.
  wwt.ctl.set_zoomMax(6 * 360);
  reaim();

  // Stash the engine's own Earth globe before any layer replaces it.
  bareGlobe = wwt.ctl.renderContext.get_backgroundImageset();

  /* Usually absent. The parent holds the globes on bare Blue Marble until the
     animation has run to 2100, then sends the layer, so there is nothing to
     apply at startup. The parameter is kept so the page is still useful on its
     own, e.g. earth-view.html?layer=SSP245%202100. */
  if (layerName) {
    applyLayer(layerName).catch((e) => console.error("temperature layer failed", e));
  }

  /* The parent swaps layers by message rather than by changing the iframe src.
     A src change reloads the page and re-downloads the 1.5 MB engine on every
     toggle click; this just changes the background imageset in place.
     Same-origin only, and the payload is a single imageset name. */
  window.addEventListener("message", (event: MessageEvent) => {
    if (event.origin !== window.location.origin) return;
    const data = event.data as { type?: string; name?: string } | null;
    if (!data || data.type !== "set-layer" || typeof data.name !== "string") return;
    applyLayer(data.name).catch((e) => console.error("layer swap failed", e));
  });

  // Tell the parent the listener is live, so it can send the current layer.
  window.parent?.postMessage({ type: "earth-view-ready" }, window.location.origin);
});
