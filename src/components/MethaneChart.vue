<template>
  <figure class="ch4-chart">
    <figcaption class="chart-title">
      Atmospheric methane, {{ firstYear }}&ndash;{{ lastYear }}
    </figcaption>

    <svg
      ref="svgEl"
      class="chart-svg"
      :viewBox="`0 0 ${W} ${H}`"
      role="img"
      :aria-label="ariaLabel"
      @pointermove="onPointerMove"
      @pointerleave="hoverIndex = null"
    >
      <!-- Recessive horizontal grid. No vertical grid: the year axis is
           continuous and the ticks carry it. -->
      <g class="grid">
        <line
          v-for="tick in yTicks"
          :key="tick.value"
          :x1="PAD_L"
          :x2="W - PAD_R"
          :y1="tick.y"
          :y2="tick.y"
        />
      </g>
      <g class="axis-label y-axis-label">
        <text
          v-for="tick in yTicks"
          :key="`y-${tick.value}`"
          :x="PAD_L - 6"
          :y="tick.y + 3"
          text-anchor="end"
        >{{ tick.value }}</text>
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

      <!-- Where methane would have stayed with no extra warming. Muted and
           dashed so it reads as a reference, not a second measurement. -->
      <line
        class="reference-line"
        :x1="PAD_L"
        :x2="W - PAD_R"
        :y1="baselineY"
        :y2="baselineY"
      />
      <!-- Right-anchored: the curve climbs away from the baseline, so the
           right end of the reference line is the clear space. On the left the
           label sat on top of the y-axis tick. -->
      <text
        class="reference-label"
        :x="W - PAD_R - 2"
        :y="baselineY - 5"
        text-anchor="end"
      >no extra warming</text>

      <path
        class="series-line"
        :d="linePath"
      />

      <!-- Direct label on the final value, so the headline number needs no
           legend and no hover. -->
      <!-- Suppressed at a single point, where the label would land on top of
           the y-axis tick it duplicates. -->
      <g v-if="points.length > 1">
        <circle
          class="series-end"
          :cx="points[points.length - 1].x"
          :cy="points[points.length - 1].y"
          r="4"
        />
        <text
          class="series-end-label"
          :x="points[points.length - 1].x - 6"
          :y="points[points.length - 1].y - 8"
          text-anchor="end"
        >{{ Math.round(series[series.length - 1].ch4Ppb) }} ppb</text>
      </g>

      <!-- Hover crosshair. -->
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
          :cy="hovered.y"
          r="5"
        />
      </g>
    </svg>

    <div
      v-if="hovered"
      class="chart-tooltip"
      :style="{ left: `${(hovered.x / W) * 100}%` }"
    >
      <strong>{{ hovered.state.year }}</strong>
      {{ Math.round(hovered.state.ch4Ppb) }} ppb
      &middot; {{ hovered.state.marshTempC.toFixed(1) }}&deg;C
    </div>
  </figure>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { YearState } from "../model";

const props = defineProps<{
  /** The run to plot, one entry per year. */
  series: YearState[];
  /** CH4 concentration the reference line sits at, ppb. */
  baselinePpb: number;
}>();

const W = 320;
const H = 150;
const PAD_L = 38;
const PAD_R = 12;
const PAD_T = 12;
const PAD_B = 22;

const svgEl = ref<SVGSVGElement | null>(null);
const hoverIndex = ref<number | null>(null);

const firstYear = computed(() => props.series[0]?.year ?? 0);
const lastYear = computed(() => props.series[props.series.length - 1]?.year ?? 0);

// The y range always contains the baseline, so a flat run still shows the
// reference line rather than scaling it off the top of the panel.
const yRange = computed(() => {
  const values = props.series.map((s) => s.ch4Ppb).concat([props.baselinePpb]);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = Math.max(30, (hi - lo) * 0.15);
  return { lo: lo - pad, hi: hi + pad };
});

function xFor(year: number): number {
  const span = lastYear.value - firstYear.value || 1;
  return PAD_L + ((year - firstYear.value) / span) * (W - PAD_L - PAD_R);
}

function yFor(ppb: number): number {
  const { lo, hi } = yRange.value;
  const fraction = (ppb - lo) / (hi - lo || 1);
  return (H - PAD_B) - fraction * (H - PAD_T - PAD_B);
}

const points = computed(() => props.series.map((s) => ({ x: xFor(s.year), y: yFor(s.ch4Ppb) })));

const linePath = computed(() => points.value.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" "));

const baselineY = computed(() => yFor(props.baselinePpb));

const yTicks = computed(() => {
  const { lo, hi } = yRange.value;
  const step = niceStep((hi - lo) / 4);
  const first = Math.ceil(lo / step) * step;
  const out: { value: number; y: number }[] = [];
  for (let v = first; v <= hi; v += step) {
    out.push({ value: Math.round(v), y: yFor(v) });
  }
  return out;
});

function niceStep(raw: number): number {
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalised = raw / magnitude;
  const snapped = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return snapped * magnitude;
}

const xTicks = computed(() => {
  const span = lastYear.value - firstYear.value;
  const step = span > 60 ? 25 : span > 24 ? 10 : 5;
  const out: { value: number; x: number }[] = [];
  for (let y = firstYear.value; y <= lastYear.value; y += step) {
    out.push({ value: y, x: xFor(y) });
  }
  return out;
});

const hovered = computed(() => {
  if (hoverIndex.value === null) return null;
  const state = props.series[hoverIndex.value];
  if (!state) return null;
  return { state, x: xFor(state.year), y: yFor(state.ch4Ppb) };
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

const ariaLabel = computed(() => {
  const last = props.series[props.series.length - 1];
  if (!last) return "Atmospheric methane over time";
  return `Atmospheric methane rises from ${Math.round(props.baselinePpb)} parts per billion in ${firstYear.value} to ${Math.round(last.ch4Ppb)} parts per billion in ${lastYear.value}.`;
});
</script>

<style lang="less">
.ch4-chart {
  --chart-surface: #122423;
  --chart-series: #d95926;
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
  margin-bottom: 0.15rem;
}

.chart-svg {
  width: 100%;
  height: auto;
  overflow: visible;
  touch-action: none;
}

.ch4-chart .grid line {
  stroke: rgba(143, 169, 174, 0.22);
  stroke-width: 1;
}

.ch4-chart .axis-label text {
  fill: var(--chart-ink-muted);
  font-size: 8px;
  font-variant-numeric: tabular-nums;
}

.reference-line {
  stroke: var(--chart-ink-muted);
  stroke-width: 1.5;
  stroke-dasharray: 4 3;
}

.reference-label {
  fill: var(--chart-ink-muted);
  font-size: 8px;
}

.series-line {
  fill: none;
  stroke: var(--chart-series);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.series-end {
  fill: var(--chart-series);
  /* 2px surface ring, so the dot stays separate from the line it sits on */
  stroke: var(--chart-surface);
  stroke-width: 2;
}

.series-end-label {
  fill: var(--chart-ink);
  font-size: 9px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.crosshair {
  stroke: var(--chart-ink-muted);
  stroke-width: 1;
}

.hover-dot {
  fill: var(--chart-series);
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
