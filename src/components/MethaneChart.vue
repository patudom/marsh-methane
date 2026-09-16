<template>
  <!-- The file is still MethaneChart.vue, but the chart is warming now. The
       name is left alone to keep the diff readable; the class is not, because a
       .ch4-chart selector styling a temperature chart is exactly the kind of
       drift that makes this project's global styles hard to follow. -->
  <figure class="warming-chart">
    <figcaption class="chart-title">Warming since 2026</figcaption>

    <!-- Legend in HTML rather than in the SVG: PAD_T is 12 units and there is
         no room inside the viewBox for two rows of text. Mandatory at two
         series. -->
    <ul class="chart-legend">
      <li>
        <span class="swatch swatch-no-feedback"></span>No methane feedback
      </li>
      <li>
        <span class="swatch swatch-feedback"></span>With methane feedback
      </li>
    </ul>

    <svg
      ref="svgEl"
      class="chart-svg"
      :viewBox="`0 0 ${W} ${H}`"
      role="img"
      :aria-label="ariaLabel"
      @pointermove="onPointerMove"
      @pointerleave="hoverIndex = null"
    >
      <g class="grid">
        <line
          v-for="tick in yTicks"
          :key="`g-${tick.y}`"
          :x1="PAD_L"
          :x2="W - PAD_R"
          :y1="tick.y"
          :y2="tick.y"
        />
      </g>
      <g class="axis-label">
        <text
          v-for="tick in yTicks"
          :key="`y-${tick.y}`"
          :x="PAD_L - 6"
          :y="tick.y + 3"
          text-anchor="end"
        >{{ tick.label }}</text>
      </g>
      <g class="axis-label">
        <text
          v-for="tick in xTicks"
          :key="`x-${tick.value}`"
          :x="tick.x"
          :y="H - PAD_B + 13"
          text-anchor="middle"
        >{{ tick.value }}</text>
      </g>

      <!-- The gap between the two lines is about 1.6 viewBox units at its
           widest, which is narrower than a single 2-unit stroke. A filled band
           is the only way it reads at all; the numeric callout below carries
           the actual magnitude. -->
      <path
        v-if="bandPath"
        class="feedback-band"
        :d="bandPath"
      />

      <path
        class="series-no-feedback"
        :d="noFeedbackPath"
      />
      <path
        class="series-feedback"
        :d="feedbackPath"
      />

      <!-- Only the feedback series is direct-labelled. Two labels 1.6 units
           apart would sit on top of each other, so the legend carries the other
           identity and the callout states the gap. -->
      <g v-if="endPoint">
        <circle
          class="series-end"
          :cx="endPoint.x"
          :cy="endPoint.y"
          r="3.5"
        />
        <text
          class="series-end-label"
          :x="endPoint.x - 6"
          :y="endPoint.y - 9"
          text-anchor="end"
        >{{ endPoint.total }}&deg;C</text>
        <text
          v-if="endPoint.gap"
          class="series-gap-label"
          :x="endPoint.x - 6"
          :y="endPoint.y - 1"
          text-anchor="end"
        >{{ endPoint.gap }} from methane</text>
      </g>

      <g v-if="hovered">
        <line
          class="crosshair"
          :x1="hovered.x"
          :x2="hovered.x"
          :y1="PAD_T"
          :y2="H - PAD_B"
        />
        <circle
          class="hover-dot"
          :cx="hovered.x"
          :cy="hovered.yFeedback"
          r="4"
        />
      </g>
    </svg>

    <div
      v-if="hovered"
      class="chart-tooltip"
      :style="{ left: `${(hovered.x / W) * 100}%` }"
    >
      <strong>{{ hovered.state.year }}</strong>
      {{ hovered.state.imposedAnomalyC.toFixed(2) }} &rarr;
      {{ hovered.state.globalAnomalyC.toFixed(2) }}&deg;C
    </div>
  </figure>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { YearState } from "../model";

const props = defineProps<{
  /** The run to plot, one entry per year. */
  series: YearState[];
}>();

const W = 320;
const H = 150;
const PAD_L = 38;
const PAD_R = 12;
const PAD_T = 12;
const PAD_B = 22;

/** Smallest span the y axis will show, deg C. Keeps a flat run legible. */
const MIN_SPAN_C = 0.4;

const svgEl = ref<SVGSVGElement | null>(null);
const hoverIndex = ref<number | null>(null);

const firstYear = computed(() => props.series[0]?.year ?? 0);
const lastYear = computed(() => props.series[props.series.length - 1]?.year ?? 0);

/**
 * The y range, in degrees rather than the parts per billion this chart used to
 * show. Zero is always included so the axis origin means something, and the
 * padding floor and the minimum span are both in degrees -- the old code had a
 * 30 ppb floor, which on a temperature axis would have spanned 60 degC.
 */
const yRange = computed(() => {
  const values = props.series.flatMap((s) => [s.imposedAnomalyC, s.globalAnomalyC]);
  let lo = Math.min(0, ...values);
  let hi = Math.max(0, ...values);

  const pad = Math.max(0.1, (hi - lo) * 0.12);
  if (hi > 0) { hi += pad; }
  if (lo < 0) { lo -= pad; }

  // A zero target leaves both series flat on the axis; centre a small window on
  // it rather than dividing by a zero span.
  if (hi - lo < MIN_SPAN_C) {
    const mid = (hi + lo) / 2;
    lo = mid - MIN_SPAN_C / 2;
    hi = mid + MIN_SPAN_C / 2;
  }
  return { lo, hi };
});

function xFor(year: number): number {
  const span = lastYear.value - firstYear.value || 1;
  return PAD_L + ((year - firstYear.value) / span) * (W - PAD_L - PAD_R);
}

function yFor(degC: number): number {
  const { lo, hi } = yRange.value;
  const fraction = (degC - lo) / (hi - lo || 1);
  return (H - PAD_B) - fraction * (H - PAD_T - PAD_B);
}

function pathFor(pick: (s: YearState) => number): string {
  return props.series
    .map((s, i) => `${i === 0 ? "M" : "L"} ${xFor(s.year).toFixed(2)} ${yFor(pick(s)).toFixed(2)}`)
    .join(" ");
}

const noFeedbackPath = computed(() => pathFor((s) => s.imposedAnomalyC));
const feedbackPath = computed(() => pathFor((s) => s.globalAnomalyC));

/** The two series joined into one closed shape, so the gap can be filled. */
const bandPath = computed(() => {
  if (props.series.length < 2) return "";
  const up = props.series
    .map((s, i) => `${i === 0 ? "M" : "L"} ${xFor(s.year).toFixed(2)} ${yFor(s.globalAnomalyC).toFixed(2)}`)
    .join(" ");
  const back = [...props.series]
    .reverse()
    .map((s) => `L ${xFor(s.year).toFixed(2)} ${yFor(s.imposedAnomalyC).toFixed(2)}`)
    .join(" ");
  return `${up} ${back} Z`;
});

const endPoint = computed(() => {
  if (props.series.length < 2) return null;
  const last = props.series[props.series.length - 1];
  const gap = last.globalAnomalyC - last.imposedAnomalyC;
  return {
    x: xFor(last.year),
    y: yFor(last.globalAnomalyC),
    total: last.globalAnomalyC.toFixed(2),
    // Suppressed when the feedback is switched off, where it would read "+0.00".
    gap: Math.abs(gap) < 0.005 ? "" : `${gap > 0 ? "+" : "−"}${Math.abs(gap).toFixed(2)}°C`,
  };
});

const yTicks = computed(() => {
  const { lo, hi } = yRange.value;
  const step = niceStep((hi - lo) / 4);
  const decimals = step < 1 ? 1 : 0;
  const first = Math.ceil(lo / step) * step;
  const out: { label: string; y: number }[] = [];
  for (let v = first; v <= hi + step * 1e-6; v += step) {
    // Rounded before labelling: the old Math.round turned 0.5-degC steps into
    // "0, 1, 1, 2, 2" and produced duplicate Vue keys.
    const value = Math.abs(v) < step * 1e-6 ? 0 : v;
    out.push({ label: value.toFixed(decimals), y: yFor(value) });
  }
  return out;
});

function niceStep(raw: number): number {
  if (!(raw > 0)) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalised = raw / magnitude;
  const snapped = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return snapped * magnitude;
}

/** Four evenly spaced years that always include both ends of the run. */
const xTicks = computed(() => {
  const span = lastYear.value - firstYear.value;
  if (span < 3) {
    return [{ value: firstYear.value, x: xFor(firstYear.value) }];
  }
  const divisions = span < 12 ? 2 : 3;
  const out: { value: number; x: number }[] = [];
  for (let i = 0; i <= divisions; i++) {
    const year = Math.round(firstYear.value + (span * i) / divisions);
    out.push({ value: year, x: xFor(year) });
  }
  return out;
});

const hovered = computed(() => {
  if (hoverIndex.value === null) return null;
  const state = props.series[hoverIndex.value];
  if (!state) return null;
  return { state, x: xFor(state.year), yFeedback: yFor(state.globalAnomalyC) };
});

function onPointerMove(event: PointerEvent) {
  const svg = svgEl.value;
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  // viewBox units, so the hit test works at any rendered size
  const x = ((event.clientX - rect.left) / rect.width) * W;
  const span = lastYear.value - firstYear.value || 1;
  const fraction = (x - PAD_L) / (W - PAD_L - PAD_R);
  const index = Math.round(fraction * span);
  hoverIndex.value = Math.max(0, Math.min(props.series.length - 1, index));
}

/**
 * Leads with the gap, because the gap is what the chart is about and a screen
 * reader cannot see two lines a pixel apart.
 */
const ariaLabel = computed(() => {
  const last = props.series[props.series.length - 1];
  if (!last || props.series.length < 2) return "Warming since 2026.";
  const gap = last.globalAnomalyC - last.imposedAnomalyC;
  if (Math.abs(gap) < 0.005) {
    return `Warming reaches ${last.imposedAnomalyC.toFixed(2)} degrees by ${lastYear.value}, with and without the marsh methane feedback.`;
  }
  return `Warming reaches ${last.imposedAnomalyC.toFixed(2)} degrees by ${lastYear.value} without the marsh methane feedback, and ${last.globalAnomalyC.toFixed(2)} degrees with it: a difference of ${Math.abs(gap).toFixed(2)} degrees.`;
});
</script>

<style lang="less">
.warming-chart {
  --chart-surface: #122423;
  --chart-no-feedback: #3987e5;
  --chart-feedback: #d95926;
  --chart-ink: #f2fbfd;
  --chart-ink-muted: #8fa9ae;

  position: relative;
  margin: 0;
  width: 100%;
}

.chart-title {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--chart-ink);
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.15rem 0.6rem;
  margin: 0.1rem 0 0.2rem;
  padding: 0;
  list-style: none;
  font-size: 0.62rem;
  color: var(--chart-ink-muted);

  li {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
}

.swatch {
  width: 0.7rem;
  height: 0;
  border-top-width: 2px;
  border-top-style: solid;
  flex: 0 0 auto;
}

/* Dashed versus solid, not just blue versus orange. Two lines this close cannot
   be told apart by hue alone. */
.swatch-no-feedback {
  border-top-color: var(--chart-no-feedback);
  border-top-style: dashed;
}

.swatch-feedback {
  border-top-color: var(--chart-feedback);
}

.chart-svg {
  width: 100%;
  height: auto;
  overflow: visible;
  touch-action: none;
}

.warming-chart .grid line {
  stroke: rgba(143, 169, 174, 0.22);
  stroke-width: 1;
}

.warming-chart .axis-label text {
  fill: var(--chart-ink-muted);
  font-size: 8px;
  font-variant-numeric: tabular-nums;
}

.series-no-feedback {
  fill: none;
  stroke: var(--chart-no-feedback);
  stroke-width: 1.5;
  stroke-dasharray: 5 3;
  stroke-linejoin: round;
}

.series-feedback {
  fill: none;
  stroke: var(--chart-feedback);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.feedback-band {
  fill: rgba(217, 89, 38, 0.35);
  stroke: none;
}

.series-end {
  fill: var(--chart-feedback);
  stroke: var(--chart-surface);
  stroke-width: 2;
}

.series-end-label {
  fill: var(--chart-ink);
  font-size: 9px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.series-gap-label {
  fill: var(--chart-feedback);
  font-size: 7.5px;
  font-variant-numeric: tabular-nums;
}

.crosshair {
  stroke: var(--chart-ink-muted);
  stroke-width: 1;
}

.hover-dot {
  fill: var(--chart-feedback);
  stroke: var(--chart-surface);
  stroke-width: 2;
}

.chart-tooltip {
  position: absolute;
  bottom: 100%;
  transform: translateX(-50%);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: #0a1716;
  border: 1px solid rgba(143, 169, 174, 0.4);
  color: var(--chart-ink);
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  pointer-events: none;
}
</style>
