<script setup lang="ts">
import { listSummarizerPresets, type SummarizerPreset } from '@/api/presets'
import { startProcessing } from '@/api/processing'
import PresetGrid from '@/components/common/PresetGrid.vue'
import PresetsFetchError from '@/components/common/PresetsFetchError.vue'
import { onMounted, ref } from 'vue'

const props = defineProps<{
  bookId: number
  /** v1.6: when true, the Start button is disabled (preflight failed). */
  startDisabled?: boolean
}>()

const emit = defineEmits<{
  select: [preset: string]
  started: [payload: { preset: string; jobId: number }]
  back: []
}>()

const presets = ref<SummarizerPreset[]>([])
const selected = ref<string | null>(null)
const loading = ref(false)
const fetchError = ref<string | null>(null)
const startError = ref<string | null>(null)
const starting = ref(false)

async function loadPresets() {
  loading.value = true
  fetchError.value = null
  try {
    const data = await listSummarizerPresets()
    presets.value = data.presets
    if (data.default_id && data.presets.some((p) => p.id === data.default_id)) {
      selected.value = data.default_id
    } else if (data.presets.length > 0) {
      selected.value = data.presets[0].id
    } else {
      selected.value = null
    }
  } catch (err) {
    fetchError.value = err instanceof Error ? err.message : 'Network error'
    presets.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadPresets)

async function handleStart() {
  if (!selected.value || starting.value || props.startDisabled) return
  starting.value = true
  startError.value = null
  try {
    const resp = await startProcessing(props.bookId, {
      preset_name: selected.value,
      run_eval: true,
      auto_retry: true,
      skip_eval: false,
    })
    emit('started', { preset: selected.value, jobId: resp.job_id })
    emit('select', selected.value)
  } catch (err) {
    startError.value = err instanceof Error ? err.message : 'Could not start processing'
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="preset-picker">
    <h2>Choose Summarization Preset</h2>
    <PresetsFetchError
      v-if="fetchError"
      :message="fetchError"
      @retry="loadPresets"
    />
    <p v-else-if="loading" class="loading">Loading presets…</p>
    <PresetGrid
      v-else
      v-model="selected"
      :presets="presets"
    />
    <p v-if="startError" class="start-error" role="alert" data-testid="start-error">
      {{ startError }}
    </p>
    <div class="form-actions">
      <button class="secondary-btn" @click="$emit('back')">Back</button>
      <button
        class="primary-btn"
        data-testid="start-processing"
        :disabled="!selected || starting || fetchError !== null || startDisabled"
        @click="handleStart"
      >
        {{ starting ? 'Starting…' : 'Start Processing' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
h2 { font-size: 1.25rem; margin-bottom: 1rem; }
.loading { opacity: 0.75; font-size: 0.9rem; }
.start-error {
  margin: 0.75rem 0 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-danger, #b91c1c);
  color: var(--color-danger, #b91c1c);
  border-radius: 0.375rem;
  background: var(--color-danger-light, #fee2e2);
  font-size: 0.85rem;
}
.preset-picker :deep(.preset-grid) { margin-bottom: 1.5rem; }
.form-actions { display: flex; justify-content: space-between; }
.primary-btn { padding: 0.5rem 1.25rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.secondary-btn { padding: 0.5rem 1.25rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; }
</style>
