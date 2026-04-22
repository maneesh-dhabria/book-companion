<script setup lang="ts">
import PresetGrid, { type PresetItem } from '@/components/common/PresetGrid.vue'
import { startProcessing } from '@/api/processing'
import { ref } from 'vue'

const props = defineProps<{
  bookId: number
}>()

const emit = defineEmits<{
  select: [preset: string]
  back: []
}>()

const selected = ref<string | null>('balanced')

const presets: PresetItem[] = [
  { id: 'balanced', label: 'Balanced', description: 'Standard detail level with good coverage' },
  { id: 'brief', label: 'Brief', description: 'Concise summaries, key points only' },
  { id: 'detailed', label: 'Detailed', description: 'Comprehensive summaries with full context' },
  {
    id: 'practitioner_bullets',
    label: 'Practitioner',
    description: 'Actionable bullet points for practitioners',
  },
]

async function handleStart() {
  if (!selected.value) return
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
    <PresetGrid v-model="selected" :presets="presets" />
    <div class="form-actions">
      <button class="secondary-btn" @click="$emit('back')">Back</button>
      <button class="primary-btn" data-testid="start-processing" @click="handleStart">
        Start Processing
      </button>
    </div>
  </div>
</template>

<style scoped>
h2 { font-size: 1.25rem; margin-bottom: 1rem; }
.preset-picker :deep(.preset-grid) { margin-bottom: 1.5rem; }
.form-actions { display: flex; justify-content: space-between; }
.primary-btn { padding: 0.5rem 1.25rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.secondary-btn { padding: 0.5rem 1.25rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; }
</style>
