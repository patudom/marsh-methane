<template>
  <div class="canister">
    <svg
      class="canister-svg"
      viewBox="0 0 140 200"
      role="img"
      :aria-label="`${bubbleCount} methane molecules bubbling out of the marsh`"
    >
      <!-- Escaping arrow, above the open top. -->
      <path
        d="M 104 30 C 112 14 124 10 132 12 M 132 12 L 124 16 M 132 12 L 130 21"
        fill="none"
        stroke="#d94f3d"
        stroke-width="3"
        stroke-linecap="round"
      />

      <!-- Beaker: open at the top, so the molecules read as escaping. -->
      <path
        d="M 22 26 L 22 178 A 6 6 0 0 0 28 184 L 106 184 A 6 6 0 0 0 112 178 L 112 26"
        fill="rgba(79, 163, 209, 0.10)"
        stroke="#5aa9d6"
        stroke-width="3"
        stroke-linejoin="round"
      />
      <!-- Elliptical rim. -->
      <ellipse
        cx="67"
        cy="26"
        rx="45"
        ry="7"
        fill="none"
        stroke="#5aa9d6"
        stroke-width="3"
      />

      <!-- Marsh sediment the methane comes out of. -->
      <path
        d="M 22 150 L 22 178 A 6 6 0 0 0 28 184 L 106 184 A 6 6 0 0 0 112 178 L 112 150 Z"
        fill="#3d3325"
      />
      <path
        d="M 22 150 Q 45 143 67 150 T 112 150"
        fill="none"
        stroke="#6b5a3e"
        stroke-width="2.5"
      />

      <g class="bubbles">
        <circle
          v-for="bubble in bubbles"
          :key="bubble.id"
          class="bubble"
          :cx="bubble.x"
          :r="bubble.r"
          cy="0"
          :style="{
            animationDuration: `${bubble.duration}s`,
            animationDelay: `${bubble.delay}s`,
          }"
        />
      </g>
    </svg>

    <div class="canister-readout">
      <div class="readout-primary">
        {{ fluxRatio.toFixed(2) }}&times;
      </div>
      <div class="readout-secondary">
        baseline CH<sub>4</sub> emission
      </div>
      <div class="readout-tertiary">
        {{ formattedMolecules }} molecules m<sup>&minus;2</sup> s<sup>&minus;1</sup>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{
  /** Emission as a multiple of the baseline emission. Drives the bubble count. */
  fluxRatio: number;
  /** CH4 molecules leaving a square metre of marsh each second, for the readout. */
  moleculesPerM2PerSec: number;
  /** How many bubbles a flux ratio of 1 draws. */
  bubblesAtBaseline?: number;
  /** Ceiling on the bubble count, so a hot run stays drawable. */
  maxBubbles?: number;
}>(), {
  bubblesAtBaseline: 9,
  maxBubbles: 60,
});

const bubbleCount = computed(() => {
  const n = Math.round(props.bubblesAtBaseline * props.fluxRatio);
  return Math.max(0, Math.min(props.maxBubbles, n));
});

/**
 * Bubble positions come from a hash of the index rather than Math.random, so a
 * bubble keeps its lane when the count changes. With random values every
 * bubble would jump each time the user moved the temperature.
 */
function pseudoRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

const bubbles = computed(() => {
  return Array.from({ length: bubbleCount.value }, (_, i) => {
    const a = pseudoRandom(i + 1);
    const b = pseudoRandom(i + 101);
    const c = pseudoRandom(i + 211);
    return {
      id: i,
      x: 32 + a * 70,
      r: 3 + b * 4,
      duration: 3.2 + c * 2.6,
      delay: -(a + b) * 3.5, // negative: the column is already full on load
    };
  });
});

const formattedMolecules = computed(() => {
  const exponent = Math.floor(Math.log10(props.moleculesPerM2PerSec));
  const mantissa = props.moleculesPerM2PerSec / Math.pow(10, exponent);
  return `${mantissa.toFixed(1)} × 10^${exponent}`;
});
</script>

<style lang="less">
.canister {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
}

.canister-svg {
  width: 100%;
  max-width: 150px;
  height: auto;
}

.bubble {
  fill: rgba(217, 89, 38, 0.25);
  stroke: #f0a878;
  stroke-width: 1.6;
  animation-name: bubble-rise;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

/* Rises from the sediment surface (y=150) out through the open rim and away.
   Fades at the top so molecules leave rather than pile up at the edge. */
@keyframes bubble-rise {
  0% {
    transform: translateY(150px);
    opacity: 0;
  }
  12% {
    opacity: 1;
  }
  80% {
    opacity: 1;
  }
  100% {
    transform: translateY(8px);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bubble {
    animation: none;
    transform: translateY(90px);
    opacity: 1;
  }
}

.canister-readout {
  text-align: center;
  line-height: 1.2;
}

.readout-tertiary {
  font-size: 0.66rem;
  color: #8fa9ae;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
