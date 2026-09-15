<template>
  <v-app
    id="app"
    :class="{ 'app-is-small': smallSize, 'app-is-portrait': isPortrait }"
  >
    <div id="main-content">
      <WorldWideTelescope :wwt-namespace="wwtNamespace"></WorldWideTelescope>

      <div id="wwt-overlay">
        <div class="overlay-row overlay-top">
          <StartingTempPanel
            v-model:starting-anomaly="startingAnomaly"
            :year="current.year"
            :running="running"
            :started="yearIndex > 0"
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
        </div>

        <div class="overlay-row overlay-bottom">
          <div class="chart-card">
            <MethaneChart
              :series="shownSeries"
              :baseline-ppb="PARAMS.baselineCh4Ppb"
            />
          </div>
        </div>
      </div>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";

import StartingTempPanel from "./components/StartingTempPanel.vue";
import Thermometer from "./components/Thermometer.vue";
import MethaneCanister from "./components/MethaneCanister.vue";
import MethaneChart from "./components/MethaneChart.vue";

import { PARAMS, runModel, type YearState } from "./model";
import { useEarthView } from "./composables/useEarthView";

defineProps<{ wwtNamespace: string }>();

const display = useDisplay();
const smallSize = computed(() => display.smAndDown.value);
const isPortrait = computed(() => display.height.value > display.width.value);

// setupEarth awaits the engine's own ready promise, so it can be fired here
// rather than watched for.
const { setupEarth } = useEarthView();
onMounted(() => { setupEarth(); });

// --- the run ---------------------------------------------------------------

/** How long one simulated year takes on screen, ms. */
const YEAR_INTERVAL_MS = 120;

const startingAnomaly = ref(2);
const run = computed<YearState[]>(() => runModel(startingAnomaly.value));

const yearIndex = ref(0);
const running = ref(false);
let timer: number | null = null;

const current = computed(() => run.value[yearIndex.value] ?? run.value[0]);

/** Only the years reached so far, so the chart draws itself as time passes. */
const shownSeries = computed(() => run.value.slice(0, yearIndex.value + 1));

function stopTimer() {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
}

function start() {
  if (running.value) return;
  if (yearIndex.value >= run.value.length - 1) { yearIndex.value = 0; }
  running.value = true;
  timer = window.setInterval(() => {
    if (yearIndex.value >= run.value.length - 1) {
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
  yearIndex.value = 0;
}

// Changing the scenario restarts the run rather than jumping mid-curve.
watch(startingAnomaly, () => reset());

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

#app > .v-application__wrap {
  flex-direction: row;
  max-height: 100svh;
}

#app {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
  font-size: var(--default-font-size);

  .wwtelescope-component {
    position: absolute;
    inset: 0;
    border-style: none;
    border-width: 0;
    margin: 0;
    padding: 0;
  }
}

#main-content {
  position: relative;
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* pointer-events: none so drags fall through to the globe. Panels re-enable
   it on themselves, and every row is content-sized -- an invisible full-height
   remainder would swallow the drag. */
#wwt-overlay {
  position: absolute;
  inset: 0;
  padding: 1rem;
  pointer-events: none;

  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.overlay-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex: 0 0 auto;
}

.overlay-bottom {
  justify-content: flex-end;
  align-items: flex-end;
}

.gauges {
  display: flex;
  gap: 0.6rem;
  align-items: stretch;
}

.gauge-card,
.chart-card {
  pointer-events: auto;
  padding: 0.7rem;
  border-radius: 8px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(3px);
  color: var(--text-color);
}

.chart-card {
  width: 22rem;
  max-width: 100%;
}

/* Portrait and small screens: stack the gauges under the controls and let the
   chart span the width, rather than three columns fighting over ~320px. */
#app.app-is-portrait,
#app.app-is-small {
  #wwt-overlay {
    padding: 0.6rem;
  }

  .overlay-top {
    flex-direction: column;
    align-items: stretch;
    gap: 0.6rem;
  }

  .control-panel {
    width: 100%;
  }

  .chart-card {
    width: 100%;
  }
}
</style>
