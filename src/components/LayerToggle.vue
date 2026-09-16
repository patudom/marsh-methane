<template>
  <!-- @keydown.stop like the other controls: without it arrow keys inside the
       toggle escape to the host page. -->
  <div
    class="layer-toggle"
    @keydown.stop
  >
    <span class="layer-toggle-label">Data layer</span>

    <!-- `mandatory` matters: without it the group can be deselected entirely,
         which hands the parent `undefined` and blanks both globe badges. -->
    <v-btn-toggle
      :model-value="year"
      mandatory
      density="compact"
      variant="outlined"
      divided
      class="layer-toggle-group"
      @update:model-value="(v: number) => emit('update:year', v)"
    >
      <v-btn
        v-for="option in YEARS"
        :key="option"
        :value="option"
        size="small"
      >
        {{ option }}
      </v-btn>
    </v-btn-toggle>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /** Which year's layer both globes are showing. */
  year: number;
}>();

const emit = defineEmits<{ "update:year": [value: number] }>();

/** The run's two end points, which are the only two layers there are. */
const YEARS = [2026, 2100];
</script>

<style lang="less">
.layer-toggle {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 0.4rem 0.7rem;
  border-radius: 8px;
  background: rgba(10, 23, 22, 0.88);
  border: 1px solid var(--border-color);
  color: var(--text-color);
}

.layer-toggle-label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8fa9ae;
}

.layer-toggle-group {
  font-variant-numeric: tabular-nums;
}
</style>
