import { engineStore } from "@wwtelescope/engine-pinia";
import { ImageSetType } from "@wwtelescope/engine-types";

/** Where the GCReW marsh is: Smithsonian Environmental Research Center, MD. */
export const GCREW_LAT = 38.8748;
export const GCREW_LON = -76.5457;

/** The Earth imageset declared in public/earth.wtml. */
const EARTH_WTML = "earth.wtml";
const EARTH_IMAGESET_NAME = "Blue Marble";

/**
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

  async function setupEarth() {
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
      raRad: (-GCREW_LON * Math.PI) / 180,
      decRad: (GCREW_LAT * Math.PI) / 180,
      zoomDeg: 60,
      instant: true,
    });
  }

  return { setupEarth, earthImagesets };
}
