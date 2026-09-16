<template>
  <div
    class="control-panel"
    @keydown.stop
  >
    <h2 class="panel-title">Temperature change by 2100</h2>

    <v-select
      :model-value="targetDeltaT"
      :items="options"
      item-title="label"
      item-value="value"
      density="compact"
      variant="outlined"
      hide-details
      class="temp-select"
      :disabled="running"
      @update:model-value="(v: number) => emit('update:targetDeltaT', v)"
    />

    <div class="panel-buttons">
      <v-btn
        :color="running ? '#8fa9ae' : '#d95926'"
        variant="flat"
        density="comfortable"
        class="flex-grow-1"
        @click="running ? emit('pause') : emit('start')"
      >
        {{ running ? "Pause" : started ? "Resume" : "Start" }}
      </v-btn>
      <v-btn
        variant="outlined"
        density="comfortable"
        icon="mdi-restore"
        size="small"
        aria-label="Reset to the starting year"
        @click="emit('reset')"
      />
    </div>

    <div class="year-readout">
      <span class="year-label">Year</span>
      <span class="year-value">{{ year }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /**
   * Warming by 2100 relative to 2026, deg C, excluding the methane feedback.
   * This is the counterfactual the user is choosing, not a starting state.
   */
  targetDeltaT: number;
  /** The year currently being shown. */
  year: number;
  /** Whether the simulation is advancing. */
  running: boolean;
  /** Whether it has been started at least once, so the button can say Resume. */
  started: boolean;
}>();

const emit = defineEmits<{
  "update:targetDeltaT": [value: number];
  start: [];
  pause: [];
  reset: [];
}>();

// A short fixed list rather than a slider: these are the scenarios worth
// talking about, and a dropdown matches the sketch.
const options = [
  { label: "−2.0 °C", value: -2 },
  { label: "−1.0 °C", value: -1 },
  { label: "−0.5 °C", value: -0.5 },
  { label: "Baseline (no change)", value: 0 },
  { label: "+0.5 °C", value: 0.5 },
  { label: "+1.0 °C", value: 1 },
  { label: "+1.5 °C", value: 1.5 },
  { label: "+2.0 °C", value: 2 },
  { label: "+3.0 °C", value: 3 },
  { label: "+4.0 °C", value: 4 },
];
</script>

<style lang="less">
.control-panel {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  /* Was 15rem inside a 16rem column, which left this card narrower than its
     siblings and wrapped the longer title onto three lines. */
  width: 100%;
  padding: 0.8rem;
  border-radius: 8px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid rgba(143, 169, 174, 0.35);
  backdrop-filter: blur(3px);
}

.panel-title {
  font-size: 1.30rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #f2fbfd;
  margin: 0;
}

.panel-buttons {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.year-readout {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-top: 0.15rem;
  border-top: 1px solid rgba(143, 169, 174, 0.25);
}

.year-label {
  font-size: 1.12rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8fa9ae;
}

.year-value {
  font-size: 1.90rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #f2fbfd;
}
</style>
