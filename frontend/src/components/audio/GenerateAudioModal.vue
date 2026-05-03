<script setup lang="ts">
import { computed, ref } from 'vue'

import { audioApi, type AudioJobRequest } from '@/api/audio'
import { estimateGenerateCost } from '@/composables/audio/useGenerateCost'
import { useAudioJobStore } from '@/stores/audioJob'

const props = withDefaults(
  defineProps<{
    open: boolean
    bookId: number
    totalUnits: number
    totalAnnotations: number
    voice?: string
    kokoroStatus?: 'warm' | 'cold' | 'not_downloaded' | 'download_failed' | null
  }>(),
  { voice: 'af_sarah', kokoroStatus: null },
)

const emit = defineEmits<{ close: []; downloadModel: [] }>()

const includeSummary = ref(true)
const includeBook = ref(true)
const includeAnnotations = ref(true)
const submitting = ref(false)
const errorMsg = ref<string | null>(null)

const jobStore = (() => {
  try {
    return useAudioJobStore()
  } catch {
    return null
  }
})()

const totalUnitsToGenerate = computed(() => {
  let n = 0
  if (includeSummary.value) n += props.totalUnits
  if (includeBook.value) n += 1
  if (includeAnnotations.value) n += props.totalAnnotations
  return n
})

const cost = computed(() => estimateGenerateCost({ totalUnits: totalUnitsToGenerate.value }))

const minutesText = computed(() => `~${cost.value.minutes.toFixed(1)} min`)
const mbText = computed(() => `~${Math.round(cost.value.megabytes)} MB`)

const needsDownload = computed(() => props.kokoroStatus === 'not_downloaded')

async function onConfirm() {
  if (submitting.value) return
  errorMsg.value = null
  submitting.value = true
  const body: AudioJobRequest = {
    scope: 'all',
    voice: props.voice,
    engine: 'kokoro',
  }
  try {
    const r = await audioApi.start(props.bookId, body)
    jobStore?.setActiveJob({
      id: r.job_id,
      status: 'RUNNING',
      completed: 0,
      total: r.total_units,
    })
    emit('close')
  } catch (err) {
    const e = err as { status?: number; body?: { existing_job_id?: number; error?: string } }
    if (e.status === 409 && e.body?.existing_job_id) {
      jobStore?.setActiveJob({
        id: e.body.existing_job_id,
        status: 'RUNNING',
        completed: 0,
        total: props.totalUnits,
      })
      emit('close')
      return
    }
    if (e.status === 503 && e.body?.error === 'ffmpeg_missing') {
      errorMsg.value = 'ffmpeg required — install with: brew install ffmpeg'
      return
    }
    errorMsg.value = e.body?.error ?? 'Failed to start audio generation'
  } finally {
    submitting.value = false
  }
}

function onDownloadModel() {
  emit('downloadModel')
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    role="dialog"
    aria-modal="true"
    aria-labelledby="gen-audio-title"
  >
    <div
      class="w-[28rem] max-w-[92vw] rounded-2xl bg-white p-5 shadow-xl ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700"
    >
      <h2 id="gen-audio-title" class="text-lg font-semibold text-slate-800 dark:text-slate-100">
        Generate audio
      </h2>

      <fieldset class="mt-3 space-y-2">
        <label class="flex items-center gap-2 text-sm">
          <input v-model="includeSummary" type="checkbox" data-testid="include-section-summaries" />
          Section summaries
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="includeBook" type="checkbox" data-testid="include-book-summary" />
          Book summary
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input
            v-model="includeAnnotations"
            type="checkbox"
            data-testid="include-annotations"
          />
          Annotations
          <span class="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            recommended
          </span>
        </label>
      </fieldset>

      <p class="mt-3 text-xs text-slate-500" data-testid="cost-estimate">
        {{ minutesText }} · {{ mbText }} for {{ totalUnits }} sections
      </p>

      <div
        v-if="needsDownload"
        class="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900"
      >
        <p>Download voice model? (~80 MB, one-time)</p>
        <button
          type="button"
          data-testid="download-model"
          class="mt-1 rounded-md bg-amber-600 px-2 py-0.5 text-white hover:bg-amber-500"
          @click="onDownloadModel"
        >
          Download model
        </button>
      </div>

      <p
        v-if="errorMsg"
        data-testid="error"
        class="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700"
      >
        {{ errorMsg }}
      </p>

      <div class="mt-4 flex justify-end gap-2">
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          data-testid="confirm"
          class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
          :disabled="submitting || (needsDownload ?? false)"
          @click="onConfirm"
        >
          Generate
        </button>
      </div>
    </div>
  </div>
</template>
