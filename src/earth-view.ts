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

wwt.waitForReady().then(() => {
  // Zoom is stored as viewport degrees times six, and the default ceiling of
  // 360 means 60 degrees. Raising it lets a tall panel pull back far enough to
  // hold the whole globe.
  wwt.ctl.set_zoomMax(6 * 360);

  wwt.gotoRADecZoom(
    // Earth mode reads the camera as (lon, lat) but still takes it through the
    // RA argument, and the engine negates on the way through, so the longitude
    // goes in with its sign flipped.
    (-lonDeg * Math.PI) / 180,
    (latDeg * Math.PI) / 180,
    zoomDeg,
    true,
  );
});
