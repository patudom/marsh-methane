<template>
  <v-app
    id="app"
    :class="{ 'app-is-small': smallSize, 'app-is-portrait': isPortrait }"
  >
    <div id="blocks">
      <!-- Block 1: everything the user drives, plus every readout. -->
      <section id="controls-block">
        <StartingTempPanel
          v-model:target-delta-t="targetDeltaT"
          :year="current.year"
          :running="running"
          :started="hasRun"
          @start="start"
          @pause="pause"
          @reset="reset"
        />

        <div class="gauges">
          <div class="gauge-card">
            <Thermometer
              :temperature="current.marshTempC"
              :baseline="PARAMS.baselineMarshTempC"
            />
          </div>
          <div class="gauge-card">
            <MethaneCanister
              :flux-ratio="current.fluxRatio"
              :molecules-per-m2-per-sec="current.moleculesPerM2PerSec"
            />
          </div>
        </div>

        <ImpactPanel
          v-model:impact-id="impactId"
          :anomaly-c="endState.globalAnomalyC"
          :year="endState.year"
        />

        <div class="chart-card">
          <MethaneChart :series="shownSeries" />
        </div>
      </section>

      <!-- Blocks 2 and 3: the same 2100 scenario without and with the marsh
           methane feedback, plus the shared layer toggle beneath them. -->
      <div id="globes-block">
        <div class="globes-row">
          <EarthPanel
            scenario="no-feedback"
            :imageset-name="leftImageset"
            :delta-t-c="endState.imposedAnomalyC"
            :layer-name="selectedImpact.label"
            :layer-year="layerYear"
            :layer-value="leftLayer.value"
            :layer-unit="leftLayer.unit"
            :layer-note="leftLayer.note"
          />
          <EarthPanel
            scenario="with-feedback"
            :imageset-name="rightImageset"
            :delta-t-c="endState.globalAnomalyC"
            :layer-name="selectedImpact.label"
            :layer-year="layerYear"
            :layer-value="rightLayer.value"
            :layer-unit="rightLayer.unit"
            :layer-note="rightLayer.note"
          />
        </div>

        <LayerToggle v-model:year="layerYear" />
      </div>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useDisplay } from "vuetify";

import StartingTempPanel from "./components/StartingTempPanel.vue";
import Thermometer from "./components/Thermometer.vue";
import MethaneCanister from "./components/MethaneCanister.vue";
import MethaneChart from "./components/MethaneChart.vue";
import ImpactPanel from "./components/ImpactPanel.vue";
import EarthPanel from "./components/EarthPanel.vue";
import LayerToggle from "./components/LayerToggle.vue";

import { PARAMS, runModel, type YearState } from "./model";
import { IMPACTS, ar6LevelFor, impactAt, isExtrapolated } from "./impacts";

const display = useDisplay();
const smallSize = computed(() => display.smAndDown.value);
const isPortrait = computed(() => display.height.value > display.width.value);

// --- the run ---------------------------------------------------------------

/** How long one simulated year takes on screen, ms. */
const YEAR_INTERVAL_MS = 120;

/** Warming by 2100 relative to 2026, excluding the methane feedback. */
const targetDeltaT = ref(2);
/** Extreme heat frequency is the opening impact; by id, not by list position. */
const impactId = ref("hot-extremes");
/** Which year's data layer both globes show. */
const layerYear = ref(2100);
/**
 * Whether the temperature maps are on the globes yet. They are held back until
 * the animation has run through to 2100, so the reveal is the payoff of playing
 * rather than something already on screen.
 */
const revealed = ref(false);

const run = computed<YearState[]>(() => runModel(targetDeltaT.value));

/* Back to opening on 2026. The globes now hold their temperature maps until the
   run reaches 2100, and that gate only makes sense from a pre-play state: the
   user presses Start, the years advance, and the data arrives on arrival. The
   globe headers and the impact panel still track the dropdown immediately, so
   the control is not inert while the animation sits at the start. */
const yearIndex = ref(0);
const running = ref(false);
/** Whether the user has actually played the animation, for the button label. */
const hasRun = ref(false);
let timer: number | null = null;

const current = computed(() => run.value[yearIndex.value] ?? run.value[0]);

/** Both globes report the run's end state, whatever year the animation is on. */
const endState = computed(() => run.value[run.value.length - 1]);

/** Only the years reached so far, so the chart draws itself as time passes. */
const shownSeries = computed(() => run.value.slice(0, yearIndex.value + 1));

// --- the data layer on the globes -----------------------------------------

const selectedImpact = computed(() => IMPACTS.find((i) => i.id === impactId.value) ?? IMPACTS[0]);

/**
 * The impact figure for one globe, formatted for its badge.
 *
 * Below the lowest published anchor the figure is withheld rather than shown.
 * `impactAt` holds flat outside the anchors, which is the right choice for the
 * readout panel but wrong on a badge labelled 2026: sea level rise would read
 * "44 cm by 2100" against a 2026 heading, which is two kinds of wrong at once.
 */
function layerFor(deltaTC: number) {
  const impact = selectedImpact.value;

  if (ar6LevelFor(deltaTC) < impact.anchors[0].ar6WarmingC) {
    return { value: "—", unit: "", note: "below the published range" };
  }

  const raw = impactAt(impact, deltaTC);
  const shown = raw.toFixed(impact.precision);
  return {
    // An explicit plus where the metric can go either way, as in the panel.
    value: raw > 0 && impact.anchors.some((a) => a.value < 0) ? `+${shown}` : shown,
    unit: impact.unit,
    note: isExtrapolated(impact, deltaTC) ? "held at the nearest studied level" : "",
  };
}

/* On 2026 both globes sit at zero warming and therefore show the same figure,
   which is the baseline half of the comparison. On 2100 they separate. */
const leftLayer = computed(() =>
  layerFor(layerYear.value === 2026 ? 0 : endState.value.imposedAnomalyC));
const rightLayer = computed(() =>
  layerFor(layerYear.value === 2026 ? 0 : endState.value.globalAnomalyC));

/**
 * Which temperature map each globe draws, by toggle position. Names match
 * public/tempmaps/index_abs.wtml.
 *
 * On 2026 both globes show the same 2030 map, which is the shared baseline. On
 * 2100 they differ: 2075 stands in for the no-feedback case and 2100 for the
 * with-feedback case, so the pair reads as the feedback pushing the world
 * further along the same scenario.
 *
 * Both are withheld until `revealed`. An empty name puts the globe back to bare
 * Blue Marble, so the maps arrive only once the run has played through to 2100.
 */
const leftImageset = computed(() => {
  if (!revealed.value) return "";
  return layerYear.value === 2026 ? "SSP245 2030" : "SSP245 2075";
});
const rightImageset = computed(() => {
  if (!revealed.value) return "";
  return layerYear.value === 2026 ? "SSP245 2030" : "SSP245 2100";
});

function stopTimer() {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
}

function start() {
  if (running.value) return;
  // Pressing Start while parked at 2100 replays from the beginning.
  if (yearIndex.value >= run.value.length - 1) { yearIndex.value = 0; }
  running.value = true;
  hasRun.value = true;
  timer = window.setInterval(() => {
    if (yearIndex.value >= run.value.length - 1) {
      // Arrived at 2100: this is what puts the maps on the globes.
      revealed.value = true;
      pause();
      return;
    }
    yearIndex.value += 1;
  }, YEAR_INTERVAL_MS);
}

function pause() {
  running.value = false;
  stopTimer();
}

function reset() {
  pause();
  hasRun.value = false;
  revealed.value = false;
  yearIndex.value = 0;
}

/* A new scenario means a new run, so it goes back to 2026 with the globes bare
   and has to be played through again. */
watch(targetDeltaT, () => reset());

onBeforeUnmount(stopTimer);
</script>

<style lang="less">
@import url("https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,200..900;1,200..900&display=swap");

:root {
  --default-font-size: clamp(0.7rem, min(1.7vh, 1.7vw), 1.1rem);
  --accent-color: #d95926;
  --background-color: #122423;
  --border-color: rgba(143, 169, 174, 0.35);
  --text-color: #f2fbfd;
  overscroll-behavior: none;
}

html {
  height: 100%;
  margin: 0;
  padding: 0;
  background-color: #000;
  overflow: hidden;
  scrollbar-width: none;
}

body {
  position: fixed;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
  font-family: "Source Sans 3", Helvetica, sans-serif;
}

/* The mount point needs a height of its own. #app is `height: 100%`, and its
   parent is this div rather than body -- a percentage against an auto-height
   parent resolves to auto, which is why the blocks were sizing to their content
   and leaving half the viewport empty. */
#app-mount {
  width: 100%;
  height: 100%;
}

#app {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
  font-size: var(--default-font-size);
}

/* A definite height, not Vuetify's `min-height: 100vh`. #blocks is `height:
   100%`, which resolves to nothing against a parent that sizes to its content
   -- the globes then collapse to their min-height and leave the viewport
   half empty. `min-height: 0` alone is not enough; the wrap needs a real
   height for the percentage to bite. */
#app > .v-application__wrap {
  height: 100%;
  min-height: 0;
  max-height: 100svh;
}

/* The three blocks. Row in landscape, column in portrait -- that is the whole
   layout. `min-width: 0` and `min-height: 0` on the children matter: without
   them a flex item refuses to shrink below its content and the last block gets
   pushed off screen. */
#blocks {
  display: flex;
  flex-direction: row;
  gap: 0.6rem;
  padding: 0.6rem;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
}

/* The controls block sizes to its content and scrolls if the viewport is too
   short for it. The globes take what is left. */
#controls-block {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  width: 16rem;
  min-height: 0;
  overflow-y: auto;
}

/* The globes and their shared toggle. Every one of these properties is
   load-bearing: the iframes chain their height by percentage all the way up to
   #blocks, so a container that sizes to its content collapses them to nothing.
   Dropping `min-height: 0` alone is enough to break it. */
#globes-block {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.globes-row {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  display: flex;
  gap: 0.6rem;
}

.gauges {
  display: flex;
  gap: 0.6rem;
  align-items: stretch;
}

.gauge-card,
.chart-card {
  padding: 0.7rem;
  border-radius: 8px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid var(--border-color);
  color: var(--text-color);
}

.gauge-card {
  flex: 1 1 0;
  min-width: 0;
}

/* Portrait: stack the blocks, and share the viewport between them rather than
   letting the page scroll. The controls are much taller than a phone screen, so
   if they kept their natural height both globes would sit below the fold and
   the three-block layout would not be visible at all. Capping them at half the
   height and scrolling inside keeps all three on screen. */
#app.app-is-portrait #blocks {
  flex-direction: column;
  overflow: hidden;

  /* Width is the abundant axis in portrait, so the four cards flow across it
     instead of stacking. That roughly halves the block's height, which is what
     keeps it inside its cap without the content looking clipped. On a phone
     there is no width to flow into and they stack again, which is why the cap
     and the inner scroll are still here. */
  #controls-block {
    flex: 0 1 auto;
    width: 100%;
    max-height: 50%;
    min-height: 0;
    overflow-y: auto;

    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-start;

    > * {
      flex: 1 1 13rem;
      min-width: 0;
    }
  }

  /* The globes stack in portrait. Without this they stay a row inside
     .globes-row and become two tall slivers on a phone. */
  .globes-row {
    flex-direction: column;
  }

  /* Lower than the 7rem it used to be: two globes plus the toggle now share
     the half of the viewport the controls leave, and the toggle is last, so it
     is what gets clipped if the globes claim too much. */
  .earth-panel {
    flex: 1 1 0;
    min-height: 5.5rem;
  }
}

/* Small screens are tight in both axes, so trim the padding and let the
   controls run full width. */
#app.app-is-small #blocks {
  gap: 0.4rem;
  padding: 0.4rem;
}

#app.app-is-small #controls-block {
  width: 100%;
}
</style>
