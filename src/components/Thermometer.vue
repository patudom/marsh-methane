<template>
  <div class="thermometer">
    <svg
      class="thermometer-svg"
      viewBox="0 0 84 220"
      role="img"
      :aria-label="`Marsh temperature ${temperature.toFixed(1)} degrees Celsius`"
    >
      <defs>
        <!-- userSpaceOnUse ties the colour scale to the temperature scale.
             With the default objectBoundingBox the gradient would stretch to
             whatever the fill rect currently is, so a cold marsh would still
             show red at the top of its short column. -->
        <linearGradient
          id="mercury-gradient"
          gradientUnits="userSpaceOnUse"
          x1="0"
          :y1="STEM_BOTTOM"
          x2="0"
          :y2="STEM_TOP"
        >
          <stop
            offset="0%"
            stop-color="#5b8f9e"
          />
          <stop
            offset="45%"
            stop-color="#e8c547"
          />
          <stop
            offset="100%"
            stop-color="#d94f3d"
          />
        </linearGradient>

        <!-- The stem and bulb as one shape, so the fill can be clipped to it
             and still look like a single column of liquid. -->
        <clipPath id="thermometer-clip">
          <path :d="outlinePath" />
        </clipPath>
      </defs>

      <path
        :d="outlinePath"
        fill="#0d1b1e"
        stroke="#cfe6ea"
        stroke-width="2.5"
      />

      <g clip-path="url(#thermometer-clip)">
        <rect
          x="0"
          :y="fillTop"
          width="60"
          :height="220 - fillTop"
          fill="url(#mercury-gradient)"
        />
      </g>

      <!-- Ticks every 5 degrees, labelled every 10. -->
      <g
        stroke="#cfe6ea"
        stroke-width="1.5"
      >
        <line
          v-for="tick in ticks"
          :key="tick.value"
          x1="38"
          :x2="tick.major ? 50 : 45"
          :y1="tick.y"
          :y2="tick.y"
        />
      </g>
      <g
        fill="#cfe6ea"
        font-size="14.4"
        text-anchor="start"
      >
        <text
          v-for="tick in ticks.filter((t) => t.major)"
          :key="`label-${tick.value}`"
          x="52"
          :y="tick.y + 5"
        >{{ tick.value }}</text>
      </g>

      <!-- Where the marsh sat before the user changed anything. -->
      <line
        x1="6"
        x2="54"
        :y1="baselineY"
        :y2="baselineY"
        stroke="#9fb8bd"
        stroke-width="1.5"
        stroke-dasharray="4 3"
      />

      <path
        :d="outlinePath"
        fill="none"
        stroke="#cfe6ea"
        stroke-width="2.5"
      />
    </svg>

    <div class="thermometer-readout">
      <div class="readout-primary">{{ temperature.toFixed(1) }}<span class="readout-unit">&deg;C</span></div>
      <div class="readout-secondary">
        <!-- A real minus character, not &minus;: inside an interpolation Vue
             escapes the entity and prints it literally. -->
        {{ anomaly >= 0 ? "+" : "−" }}{{ Math.abs(anomaly).toFixed(2) }}&deg;C vs. baseline
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{
  /** Marsh temperature to display, deg C. */
  temperature: number;
  /** Temperature the dashed baseline marker sits at, deg C. */
  baseline: number;
  /** Bottom of the displayed scale, deg C. */
  min?: number;
  /** Top of the displayed scale, deg C. */
  max?: number;
}>(), {
  /* Narrowed from 10-40. The marsh used to jump to its final temperature the
     moment the dropdown changed; now it ramps from 21.5 to at most 25.6, and on
     a 30-degree scale that travel was under 7% of the column. This range still
     contains every scenario, from the -2 case at 19.5 to the +4 case at 25.6. */
  min: 18,
  max: 28,
});

const anomaly = computed(() => props.temperature - props.baseline);

// Stem from y=14 to y=180, bulb centred at y=192. The path is a rounded stem
// merged into the bulb circle; both get the same clip so the liquid is one
// continuous column.
const outlinePath = "M 22 20 A 8 8 0 0 1 38 20 L 38 176 A 16 16 0 1 1 22 176 Z";

const STEM_TOP = 20;
const STEM_BOTTOM = 176;

function yFor(value: number): number {
  const fraction = (value - props.min) / (props.max - props.min);
  const clamped = Math.max(0, Math.min(1, fraction));
  return STEM_BOTTOM - clamped * (STEM_BOTTOM - STEM_TOP);
}

const fillTop = computed(() => yFor(props.temperature));
const baselineY = computed(() => yFor(props.baseline));

/* Step chosen from the span rather than fixed at 5. On the old 10-40 scale a
   5-degree step gave a sensible ladder; on the narrower scale it left a single
   labelled tick. */
const ticks = computed(() => {
  const span = props.max - props.min;
  const step = span > 20 ? 5 : 2;
  const labelEvery = step * 2;

  const out: { value: number; y: number; major: boolean }[] = [];
  const first = Math.ceil(props.min / step) * step;
  for (let v = first; v <= props.max; v += step) {
    out.push({ value: v, y: yFor(v), major: v % labelEvery === 0 });
  }
  return out;
});
</script>

<style lang="less">
.thermometer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
}

.thermometer-svg {
  width: 100%;
  max-width: 104px;
  height: auto;
}

.thermometer-readout {
  text-align: center;
  line-height: 1.15;
}

.readout-primary {
  font-size: 2.00rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #f2fbfd;
}

.readout-unit {
  font-size: 1.15rem;
  font-weight: 500;
  margin-left: 0.1em;
}

.readout-secondary {
  font-size: 1.15rem;
  color: #a8c4c9;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
