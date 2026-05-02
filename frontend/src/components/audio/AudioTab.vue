<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { audioApi, type AudioInventoryItem } from '@/api/audio'
import { useAudioJobStore } from '@/stores/audioJob'

const props = defineProps<{ bookId: number }>()

const files = ref<AudioInventoryItem[]>([])
const coverage = ref<{ total: number; generated: number; stale?: number }>({
  total: 0,
  generated: 0,
})
const loaded = ref(false)
const error = ref<string | null>(null)

const jobStore = (() => {
  try {
    return useAudioJobStore()
  } catch {
    return null
  }
})()

const isGenerating = computed(
  () =>
    jobStore?.activeJob &&
    (jobStore.activeJob.status === 'RUNNING' || jobStore.activeJob.status === 'PENDING'),
)

const state = computed<'no-audio' | 'partial' | 'full' | 'generating'>(() => {
  if (isGenerating.value) return 'generating'
  if (coverage.value.generated === 0) return 'no-audio'
  if (coverage.value.generated >= coverage.value.total && coverage.value.total > 0) return 'full'
  return 'partial'
})

async function load() {
  try {
    const inv = await audioApi.inventory(props.bookId)
    files.value = inv.files
    coverage.value = inv.coverage
    loaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'failed to load'
    loaded.value = true
  }
}

async function onCancelJob() {
  const id = jobStore?.activeJob?.id
  if (!id) return
  try {
    await fetch(`/api/v1/jobs/${id}/cancel`, { method: 'POST' })
    jobStore?.clear()
  } catch {
    /* toast handled elsewhere */
  }
}

function onGenerate() {
  // GenerateAudioModal opens via parent; this event is consumed by the host.
  // For the placeholder D2 surface, no-op until D5 wires the modal.
}

onMounted(load)
</script>

<template>
  <div class="audio-tab" data-testid="audio-tab">
    <div v-if="!loaded" class="text-sm text-slate-500">Loading audio inventory…</div>

    <div v-else-if="state === 'generating'" data-testid="state-generating">
      <p class="text-sm text-slate-700">
        Generating audio: {{ jobStore?.activeJob?.completed ?? 0 }} /
        {{ jobStore?.activeJob?.total ?? 0 }}
      </p>
      <button
        type="button"
        data-testid="cancel-job"
        class="rounded-md bg-slate-100 px-3 py-1 text-sm text-slate-700 hover:bg-slate-200"
        @click="onCancelJob"
      >
        Cancel
      </button>
    </div>

    <div v-else-if="state === 'no-audio'" data-testid="state-no-audio">
      <p class="text-sm text-slate-700">No audio yet for this book.</p>
      <button
        type="button"
        data-testid="generate-audio"
        class="mt-2 rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500"
        @click="onGenerate"
      >
        Generate audio
      </button>
    </div>

    <div v-else-if="state === 'partial'" data-testid="state-partial">
      <p class="text-sm text-slate-700">
        {{ coverage.generated }} of {{ coverage.total }} sections have audio.
      </p>
      <div
        data-testid="coverage-bar"
        class="mt-1 h-2 w-full rounded bg-slate-200"
        role="progressbar"
        :aria-valuenow="coverage.generated"
        :aria-valuemax="coverage.total"
      >
        <div
          class="h-full rounded bg-indigo-600"
          :style="{
            width: coverage.total > 0 ? `${(coverage.generated / coverage.total) * 100}%` : '0%',
          }"
        />
      </div>
    </div>

    <div v-else-if="state === 'full'" data-testid="state-full">
      <p class="text-sm text-slate-700">
        All {{ coverage.total }} sections have audio.
      </p>
    </div>
  </div>
</template>
