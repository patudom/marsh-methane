import { engineStore } from "@wwtelescope/engine-pinia";
import { ImageSetType } from "@wwtelescope/engine-types";

/** Where the GCReW marsh is: Smithsonian Environmental Research Center, MD. */
export const GCREW_LAT = 38.8748;
export const GCREW_LON = -76.5457;

/** The Earth imageset declared in public/earth.wtml. */
const EARTH_WTML = "earth.wtml";
const EARTH_IMAGESET_NAME = "Blue Marble";

/** Where a globe should be pointed. Degrees; zoomDeg is the viewport height. */
export interface EarthCamera {
  latDeg?: number;
  lonDeg?: number;
  /** The engine clamps this at 60, which is the whole disk and no further. */
  zoomDeg?: number;
}

/**
 * NO LONGER USED by the app, and kept only as reference.
 *
 * Both globes now live in iframes running earth-view.html, which drives a raw
 * WWTInstance and can therefore boot with `startMode: "earth"` instead of
 * loading public/earth.wtml. This composable is the pinia-store version of the
 * same thing, and it only works in a realm where wwtPinia is installed -- which
 * main.ts no longer does. It is worth keeping because attaching a data layer to
 * the Earth frame will go through a store like this one.
 *
 * Puts WWT into its Earth view.
 *
 * WWT has no separate "show the globe" call: the render mode is read straight
 * off the background imageset's type, so installing one whose type is `earth`
 * is what switches the view. The engine builds its own Blue Marble imageset
 * only when booted with startMode "earth", which engine-pinia's component
 * never does, so the imageset is loaded from our own WTML first.
 */
export function useEarthView() {
  const store = engineStore();

  function earthImagesets(): string[] {
    return store.availableImagesets
      .filter((info) => info.type === ImageSetType.earth)
      .map((info) => info.name);
  }

  async function setupEarth(camera: EarthCamera = {}) {
    const {
      latDeg = GCREW_LAT,
      lonDeg = GCREW_LON,
      zoomDeg = 60,
    } = camera;

    await store.waitForReady();

    if (!earthImagesets().includes(EARTH_IMAGESET_NAME)) {
      await store.loadImageCollection({ url: EARTH_WTML, loadChildFolders: false });
    }

    const available = earthImagesets();
    if (available.length === 0) {
      console.warn("No Earth imageset available; staying in sky view.");
      return;
    }

    store.setBackgroundImageByName(
      available.includes(EARTH_IMAGESET_NAME) ? EARTH_IMAGESET_NAME : available[0]
    );

    // In Earth mode the camera is (lon, lat), but it still arrives through the
    // RA/Dec arguments. The engine's rAtoViewLng negates on the way through
    // (lng = -ra_deg), so the longitude has to go in with its sign flipped.
    // zoomDeg is the viewport height and the engine clamps it at 60, which is
    // as far out as an Earth view goes -- the whole disk, and no further.
    store.gotoRADecZoom({
      raRad: (-lonDeg * Math.PI) / 180,
      decRad: (latDeg * Math.PI) / 180,
      zoomDeg,
      instant: true,
    });
  }

  return { setupEarth, earthImagesets };
}
