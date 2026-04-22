<script setup lang="ts">
export interface PresetItem {
  id: string
  label: string
  description: string
}

defineProps<{
  presets: PresetItem[]
  modelValue: string | null
}>()

defineEmits<{
  'update:modelValue': [id: string]
}>()
</script>

<template>
  <div class="preset-grid">
    <button
      v-for="preset in presets"
      :key="preset.id"
      type="button"
      data-testid="preset-card"
      class="preset-card"
      :class="{ selected: modelValue === preset.id }"
      @click="$emit('update:modelValue', preset.id)"
    >
      <span class="preset-label">{{ preset.label }}</span>
      <span class="preset-desc">{{ preset.description }}</span>
    </button>
  </div>
</template>

<style scoped>
.preset-grid {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.preset-card {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 0.25rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.5rem;
  cursor: pointer;
  background: none;
  font: inherit;
  color: inherit;
}
.preset-card.selected {
  border-color: var(--color-primary, #3b82f6);
  background: var(--color-primary-light, #eff6ff);
}
.preset-label { font-weight: 500; font-size: 0.9rem; }
.preset-desc { font-size: 0.8rem; color: var(--color-text-secondary, #888); }
</style>
