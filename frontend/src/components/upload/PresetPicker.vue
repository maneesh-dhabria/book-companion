<script setup lang="ts">
import { startProcessing } from '@/api/processing'
import { ref } from 'vue'

const props = defineProps<{
  bookId: number
}>()

const emit = defineEmits<{
  select: [preset: string]
  back: []
}>()

const selected = ref('balanced')

const presets = [
  { name: 'balanced', label: 'Balanced', description: 'Standard detail level with good coverage' },
  { name: 'brief', label: 'Brief', description: 'Concise summaries, key points only' },
  { name: 'detailed', label: 'Detailed', description: 'Comprehensive summaries with full context' },
  {
    name: 'practitioner_bullets',
    label: 'Practitioner',
    description: 'Actionable bullet points for practitioners',
  },
]

async function handleStart() {
  await startProcessing(props.bookId, {
    preset_name: selected.value,
    run_eval: true,
    auto_retry: true,
    skip_eval: false,
  })
  emit('select', selected.value)
}
</script>

<template>
  <div class="preset-picker">
    <h2>Choose Summarization Preset</h2>
    <div class="preset-options">
      <label
        v-for="preset in presets"
        :key="preset.name"
        class="preset-option"
        :class="{ selected: selected === preset.name }"
      >
        <input type="radio" v-model="selected" :value="preset.name" />
        <div class="preset-info">
          <span class="preset-label">{{ preset.label }}</span>
          <span class="preset-desc">{{ preset.description }}</span>
        </div>
      </label>
    </div>
    <div class="form-actions">
      <button class="secondary-btn" @click="$emit('back')">Back</button>
      <button class="primary-btn" @click="handleStart">Start Processing</button>
    </div>
  </div>
</template>

<style scoped>
h2 { font-size: 1.25rem; margin-bottom: 1rem; }
.preset-options { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem; }
.preset-option { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.5rem; cursor: pointer; }
.preset-option.selected { border-color: var(--color-primary, #3b82f6); background: var(--color-primary-light, #eff6ff); }
.preset-option input { margin-top: 0.25rem; }
.preset-info { display: flex; flex-direction: column; }
.preset-label { font-weight: 500; font-size: 0.9rem; }
.preset-desc { font-size: 0.8rem; color: var(--color-text-secondary, #888); }
.form-actions { display: flex; justify-content: space-between; }
.primary-btn { padding: 0.5rem 1.25rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.secondary-btn { padding: 0.5rem 1.25rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; }
</style>
