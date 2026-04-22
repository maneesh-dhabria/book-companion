<script setup lang="ts">
import { listSummarizerPresets, type SummarizerPreset } from '@/api/presets'
import PresetGrid from '@/components/common/PresetGrid.vue'
import PresetsFetchError from '@/components/common/PresetsFetchError.vue'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{
  /** Id of the preset to pre-select. Defaults to server-returned `default_id`. */
  preselect?: string | null
  /** Modal title. */
  title?: string
  /** Submit button label. */
  submitLabel?: string
}>()

const emit = defineEmits<{
  submit: [presetId: string]
  cancel: []
}>()

const presets = ref<SummarizerPreset[]>([])
const selected = ref<string | null>(null)
const loading = ref(false)
const fetchError = ref<string | null>(null)

async function load() {
  loading.value = true
  fetchError.value = null
  try {
    const data = await listSummarizerPresets()
    presets.value = data.presets
    if (props.preselect && data.presets.some((p) => p.id === props.preselect)) {
      selected.value = props.preselect
    } else if (data.default_id && data.presets.some((p) => p.id === data.default_id)) {
      selected.value = data.default_id
    } else if (data.presets.length > 0) {
      selected.value = data.presets[0].id
    }
  } catch (err) {
    fetchError.value = err instanceof Error ? err.message : 'Network error'
    presets.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.preselect, load)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('cancel')
  } else if (e.key === 'Enter' && selected.value) {
    emit('submit', selected.value)
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

function onSubmit() {
  if (selected.value) emit('submit', selected.value)
}
</script>

<template>
  <div class="modal-overlay" role="dialog" aria-modal="true" @click.self="emit('cancel')">
    <div class="modal-body">
      <h3 class="modal-title">{{ title || 'Choose a summarization preset' }}</h3>
      <PresetsFetchError
        v-if="fetchError"
        :message="fetchError"
        @retry="load"
      />
      <p v-else-if="loading" class="loading">Loading presets…</p>
      <PresetGrid
        v-else
        v-model="selected"
        :presets="presets"
      />
      <div class="modal-actions">
        <button type="button" class="secondary-btn" @click="emit('cancel')">
          Cancel
        </button>
        <button
          type="button"
          data-testid="submit"
          class="primary-btn"
          :disabled="!selected || fetchError !== null"
          @click="onSubmit"
        >
          {{ submitLabel || 'Generate' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal-body {
  width: min(480px, 92vw);
  max-height: 90vh;
  overflow: auto;
  background: var(--color-bg-primary, #fff);
  color: var(--color-text-primary, #111);
  border-radius: 0.75rem;
  padding: 1.25rem 1.25rem 1rem;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.modal-title { margin: 0; font-size: 1.1rem; font-weight: 600; }
.loading { opacity: 0.75; font-size: 0.9rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
.primary-btn { padding: 0.5rem 1rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.secondary-btn { padding: 0.5rem 1rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; color: inherit; cursor: pointer; }
</style>
