<script setup lang="ts">
defineProps<{
  palette: readonly string[]
  modelValue: string
  ariaLabelPrefix: string
}>()

defineEmits<{ (e: 'update:modelValue', v: string): void }>()
</script>

<template>
  <div class="swatch-row">
    <button
      v-for="c in palette"
      :key="c"
      type="button"
      class="swatch"
      :class="{ active: modelValue === c }"
      :style="{ background: c }"
      :aria-label="`${ariaLabelPrefix} ${c}`"
      @click="$emit('update:modelValue', c)"
    />
  </div>
</template>

<style scoped>
.swatch-row {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.swatch {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}
.swatch.active {
  border-color: var(--color-primary, #4f46e5);
}
.swatch:focus-visible {
  outline: 2px solid var(--color-primary, #4f46e5);
  outline-offset: 2px;
}
</style>
