<template>
  <div class="canister">
    <svg
      class="canister-svg"
      viewBox="0 0 140 200"
      role="img"
      :aria-label="`${moleculeCount} methane molecules in the marsh container`"
    >
      <!-- The cylinder is drawn back-to-front: far rim, body, sediment, then
           near rim, so the sediment sits inside the glass rather than on it. -->

      <!-- Far half of the bottom ellipse, faint: it reads through the glass. -->
      <path
        d="M 22 178 A 45 7 0 0 1 112 178"
        fill="none"
        stroke="#5aa9d6"
        stroke-width="2"
        opacity="0.45"
      />

      <!-- Body: straight sides closed by the near half of the bottom ellipse. -->
      <path
        d="M 22 26 L 22 178 A 45 7 0 0 0 112 178 L 112 26"
        fill="rgba(79, 163, 209, 0.10)"
        stroke="#5aa9d6"
        stroke-width="3"
        stroke-linejoin="round"
      />

      <!-- Marsh sediment, clipped to the cylinder so it takes the curved base. -->
      <g clip-path="url(#cylinder-clip)">
        <rect
          x="22"
          y="150"
          width="90"
          height="40"
          fill="#3d3325"
        />
      </g>
      <path
        d="M 22 150 Q 45 143 67 150 T 112 150"
        fill="none"
        stroke="#6b5a3e"
        stroke-width="2.5"
      />

      <!-- Open rim last, so it sits in front of everything inside. -->
      <ellipse
        cx="67"
        cy="26"
        rx="45"
        ry="7"
        fill="none"
        stroke="#5aa9d6"
        stroke-width="3"
      />

      <defs>
        <clipPath id="cylinder-clip">
          <!-- Rect plus bottom ellipse union to the cylinder silhouette. -->
          <rect
            x="22"
            y="26"
            width="90"
            height="152"
          />
          <ellipse
            cx="67"
            cy="178"
            rx="45"
            ry="7"
          />
        </clipPath>
      </defs>

      <!-- One cartoon CH4 per molecule: a carbon with four hydrogens. The outer
           group places and rotates it, the inner one bobs, so the two
           transforms do not fight. -->
      <g
        v-for="molecule in molecules"
        :key="molecule.id"
        :transform="`translate(${molecule.x} ${molecule.y}) rotate(${molecule.rotation})`"
      >
        <g
          class="molecule"
          :style="{
            animationDuration: `${molecule.duration}s`,
            animationDelay: `${molecule.delay}s`,
          }"
        >
          <line
            v-for="(hydrogen, index) in HYDROGENS"
            :key="`bond-${index}`"
            class="molecule-bond"
            x1="0"
            y1="0"
            :x2="hydrogen.x"
            :y2="hydrogen.y"
          />
          <circle
            v-for="(hydrogen, index) in HYDROGENS"
            :key="`h-${index}`"
            class="molecule-hydrogen"
            :cx="hydrogen.x"
            :cy="hydrogen.y"
            r="1.9"
          />
          <circle
            class="molecule-carbon"
            cx="0"
            cy="0"
            r="3.9"
          />
        </g>
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
  /** Emission as a multiple of the baseline emission. Drives the molecule count. */
  fluxRatio: number;
  /** CH4 molecules leaving a square metre of marsh each second, for the readout. */
  moleculesPerM2PerSec: number;
  /** How many molecules a flux ratio of 1 draws. */
  moleculesAtBaseline?: number;
}>(), {
  moleculesAtBaseline: 9,
});

/** Hydrogen offsets from the carbon, in viewBox units. */
const HYDROGENS = [
  { x: 0, y: -6.4 },
  { x: 6.4, y: 0 },
  { x: 0, y: 6.4 },
  { x: -6.4, y: 0 },
];

// The interior the molecules may occupy: inside the glass, above the sediment,
// inset by roughly one molecule radius so none straddles a wall. The grid is
// sized so a whole molecule fits inside one cell, which is what keeps
// neighbours from overlapping.
const COLUMNS = 4;
const ROWS = 5;
const X_MIN = 30, X_MAX = 104;
const Y_MIN = 38, Y_MAX = 142;

/** Ceiling on the count: one molecule per cell of the placement grid. */
const MAX_MOLECULES = COLUMNS * ROWS;

const moleculeCount = computed(() => {
  const n = Math.round(props.moleculesAtBaseline * props.fluxRatio);
  return Math.max(0, Math.min(MAX_MOLECULES, n));
});

/** Deterministic hash, so a molecule keeps its spot when the count changes. */
function pseudoRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

interface MoleculePosition {
  x: number;
  y: number;
  rotation: number;
  duration: number;
  delay: number;
}

/**
 * A fixed pool of scattered positions, taken in order.
 *
 * Jittered grid rather than plain random placement: with pure random x and y a
 * dozen molecules clump and overlap badly at this size. One per cell keeps them
 * apart, and the jitter stops it reading as a grid. The pool is built once and
 * the draw takes the first N, so raising the count adds molecules without
 * moving the ones already on screen.
 */
const POSITIONS = (() => {
  const cellWidth = (X_MAX - X_MIN) / COLUMNS;
  const cellHeight = (Y_MAX - Y_MIN) / ROWS;

  const cells: MoleculePosition[] = [];
  for (let row = 0; row < ROWS; row++) {
    for (let column = 0; column < COLUMNS; column++) {
      const index = row * COLUMNS + column;
      cells.push({
        x: X_MIN + (column + 0.5) * cellWidth + (pseudoRandom(index + 1) - 0.5) * cellWidth * 0.35,
        y: Y_MIN + (row + 0.5) * cellHeight + (pseudoRandom(index + 71) - 0.5) * cellHeight * 0.35,
        rotation: pseudoRandom(index + 141) * 90,
        duration: 3.4 + pseudoRandom(index + 211) * 2.8,
        delay: -pseudoRandom(index + 281) * 5,
      });
    }
  }

  /* Farthest-point ordering, so that *every* prefix of the pool is spread
     through the container. A plain hash shuffle also scatters the cells, but
     any given prefix of it can come out lopsided -- twelve molecules crowding
     one corner and leaving another empty, which is what it did here. Greedily
     taking the cell farthest from everything already placed fixes that at all
     counts, and 20 cells makes the quadratic cost irrelevant. */
  const ordered: MoleculePosition[] = [cells.splice(9, 1)[0]]; // start mid-grid
  while (cells.length > 0) {
    let bestIndex = 0;
    let bestDistance = -1;
    cells.forEach((candidate, i) => {
      const nearest = Math.min(...ordered.map((placed) =>
        (placed.x - candidate.x) ** 2 + (placed.y - candidate.y) ** 2));
      if (nearest > bestDistance) {
        bestDistance = nearest;
        bestIndex = i;
      }
    });
    ordered.push(cells.splice(bestIndex, 1)[0]);
  }
  return ordered;
})();

const molecules = computed(() =>
  POSITIONS.slice(0, moleculeCount.value).map((position, i) => ({ id: i, ...position }))
);

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

.molecule-carbon {
  fill: #d95926;
  stroke: #7d2d12;
  stroke-width: 1;
}

.molecule-hydrogen {
  fill: #ffd9c2;
  stroke: #b9713f;
  stroke-width: 0.9;
}

.molecule-bond {
  stroke: #f0a878;
  stroke-width: 1.5;
  stroke-linecap: round;
}

/* Drifting in place rather than rising in a column: the molecules are spread
   through the container, so a shared upward sweep would undo that. */
.molecule {
  animation-name: molecule-drift;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
  animation-direction: alternate;
}

@keyframes molecule-drift {
  from {
    transform: translate(-1.5px, 2.5px);
  }
  to {
    transform: translate(1.5px, -2.5px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .molecule {
    animation: none;
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
