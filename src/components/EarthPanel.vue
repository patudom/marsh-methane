<template>
  <section class="earth-panel">
    <!-- An iframe, not a second <WorldWideTelescope>: the engine keeps its
         control object in a module global, so two views need two JS realms.
         See vite.config.mts. -->
    <iframe
      class="earth-frame"
      :src="frameSrc"
      :title="`Earth, ${scenarioText}`"
      loading="eager"
    />

    <header class="earth-label">
      <span class="earth-label-temp">{{ formattedDelta }}&deg;C by 2100</span>
      <span class="earth-label-scenario">{{ scenarioText }}</span>
    </header>

    <!-- The data layer. The globe itself is plain Blue Marble: there is no
         gridded dataset in the project, so the layer is reported as a figure
         rather than drawn as if it were geography. -->
    <footer class="earth-layer">
      <span class="earth-layer-name">{{ layerName }} &middot; {{ layerYear }}</span>
      <span class="earth-layer-value">
        {{ layerValue }}<span
          v-if="layerUnit"
          class="earth-layer-unit"
        > {{ layerUnit }}</span>
      </span>
      <span
        v-if="layerNote"
        class="earth-layer-note"
      >{{ layerNote }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{
  /** Warming this globe represents, deg C by 2100 relative to 2026. */
  deltaTC: number;
  /** Which of the two runs this globe is. */
  scenario: "no-feedback" | "with-feedback";
  /** Name of the quantity the layer shows, from the impact dropdown. */
  layerName: string;
  /** Year the layer represents. */
  layerYear: number;
  /** The figure, already formatted by the parent, or an em dash. */
  layerValue: string;
  /** Unit for the figure. May be empty. */
  layerUnit?: string;
  /** Caveat line, e.g. when the warming level sits outside the published range. */
  layerNote?: string;
  /** Camera centre. Defaults to the marsh, set by the iframe page. */
  latDeg?: number;
  lonDeg?: number;
}>(), {
  layerUnit: "",
  layerNote: "",
  latDeg: undefined,
  lonDeg: undefined,
});

const scenarioText = computed(() =>
  props.scenario === "with-feedback" ? "with methane feedback" : "no methane feedback");

/**
 * Two decimals, not one. The feedback is worth about 0.04 degC, so at one
 * decimal both globes round to the same number and the comparison the panel
 * exists to make disappears. Sign shown only when negative.
 */
const formattedDelta = computed(() =>
  `${props.deltaTC < 0 ? "−" : ""}${Math.abs(props.deltaTC).toFixed(2)}`);

/**
 * Built once and never changed. Putting reactive state in the iframe URL would
 * reload the page and re-download the engine on every model tick, so the globes
 * are static and the overlays carry the changing numbers.
 */
const frameSrc = computed(() => {
  const params = new URLSearchParams();
  if (props.latDeg !== undefined) { params.set("lat", String(props.latDeg)); }
  if (props.lonDeg !== undefined) { params.set("lon", String(props.lonDeg)); }
  const query = params.toString();
  return query.length > 0 ? `earth-view.html?${query}` : "earth-view.html";
});
</script>

<style lang="less">
.earth-panel {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #000;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.earth-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: none;
}

/* Both overlays are capped: the panel is overflow: hidden and these strings are
   long enough to run off a narrow globe otherwise. */
.earth-label,
.earth-layer {
  position: absolute;
  left: 0.6rem;
  max-width: calc(100% - 1.2rem);
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  padding: 0.35rem 0.55rem;
  border-radius: 6px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(3px);
  color: var(--text-color);
  pointer-events: none;
}

.earth-label {
  top: 0.6rem;
}

.earth-layer {
  bottom: 0.6rem;
}

.earth-label-temp {
  font-size: 1.05rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.earth-label-scenario {
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8fa9ae;
}

.earth-layer-name {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #8fa9ae;
}

.earth-layer-value {
  font-size: 0.9rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #f0a878;
}

.earth-layer-unit {
  font-size: 0.6rem;
  font-weight: 400;
  color: #a8c4c9;
}

.earth-layer-note {
  font-size: 0.56rem;
  font-style: italic;
  color: #7d949a;
}
</style>
