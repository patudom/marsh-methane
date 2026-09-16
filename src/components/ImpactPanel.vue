<template>
  <div
    class="impact-panel"
    @keydown.stop
  >
    <h2 class="panel-title">Human impact</h2>

    <v-select
      :model-value="impactId"
      :items="IMPACTS"
      item-title="label"
      item-value="id"
      density="compact"
      variant="outlined"
      hide-details
      class="impact-select"
      @update:model-value="(id: string) => emit('update:impactId', id)"
    />

    <div class="impact-readout">
      <div class="impact-value">
        {{ formattedValue }}
      </div>
      <div class="impact-unit">{{ impact.unit }}</div>
    </div>

    <p class="impact-note">{{ impact.note }}</p>

    <!-- Both baselines, deliberately. The model works in anomalies above 2019
         while every IPCC warming level is against 1850-1900, and the gap is
         1.09 degC. Showing only one number invites reading an AR6 figure off
         the wrong scale. -->
    <p class="impact-basis">
      at {{ anomalyC >= 0 ? "+" : "−" }}{{ Math.abs(anomalyC).toFixed(2) }}&deg;C vs. today
      in {{ year }}, i.e. {{ ar6Level.toFixed(1) }}&deg;C vs. 1850&ndash;1900
    </p>

    <p class="impact-source">
      {{ impact.source }}
      <span v-if="extrapolated">&middot; held at the nearest studied level</span>
    </p>

    <p
      v-if="!impact.published"
      class="impact-warning"
    >
      Derived, not published at these levels
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { IMPACTS, impactAt, isExtrapolated, ar6LevelFor } from "../impacts";

const props = defineProps<{
  /** Which impact is selected. */
  impactId: string;
  /** Warming level the impact is evaluated at, deg C. */
  anomalyC: number;
  /** The year that warming level belongs to. */
  year: number;
}>();

const emit = defineEmits<{ "update:impactId": [value: string] }>();

const impact = computed(() => IMPACTS.find((i) => i.id === props.impactId) ?? IMPACTS[0]);

const value = computed(() => impactAt(impact.value, props.anomalyC));
const extrapolated = computed(() => isExtrapolated(impact.value, props.anomalyC));
const ar6Level = computed(() => ar6LevelFor(props.anomalyC));

const formattedValue = computed(() => {
  const v = value.value;
  const shown = v.toFixed(impact.value.precision);
  // An explicit plus on a gain reads better next to the losses, which already
  // carry their own sign.
  return v > 0 && impact.value.anchors.some((a) => a.value < 0) ? `+${shown}` : shown;
});
</script>

<style lang="less">
.impact-panel {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.8rem;
  border-radius: 8px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(3px);
  color: var(--text-color);
}

.impact-readout {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}

.impact-value {
  font-size: 1.6rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  color: #f0a878;
}

.impact-unit {
  font-size: 0.7rem;
  color: #a8c4c9;
}

.impact-note {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.25;
  color: #a8c4c9;
}

.impact-basis {
  margin: 0;
  font-size: 0.66rem;
  line-height: 1.25;
  color: #8fa9ae;
  font-variant-numeric: tabular-nums;
}

.impact-source {
  margin: 0;
  font-size: 0.62rem;
  line-height: 1.25;
  color: #7d949a;
}

.impact-warning {
  margin: 0;
  font-size: 0.62rem;
  font-style: italic;
  color: #d98a6a;
}
</style>
