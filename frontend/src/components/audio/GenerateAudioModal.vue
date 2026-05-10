<script setup lang="ts">
import { computed, ref } from 'vue'

import { audioApi, type AudioJobRequest } from '@/api/audio'
import { estimateGenerateCost } from '@/composables/audio/useGenerateCost'
import { useAudioJobStore } from '@/stores/audioJob'
import { useSettingsStore } from '@/stores/settings'

const props = withDefaults(
  defineProps<{
    open: boolean
    bookId: number
    totalUnits: number
    totalAnnotations: number
    generatedCount?: number
    bookSummaryGenerated?: boolean
    totalWordCount?: number
    voice?: string
    kokoroStatus?: 'warm' | 'cold' | 'not_downloaded' | 'download_failed' | null
  }>(),
  {
    voice: 'af_sarah',
    kokoroStatus: null,
    generatedCount: 0,
    bookSummaryGenerated: false,
    totalWordCount: 0,
  },
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

const settingsStore = (() => {
  try {
    return useSettingsStore()
  } catch {
    return null
  }
})()

// FR-13: delta-aware contribution per content kind. X/Z are computed from
// the user's enabled deltas (sections-missing-audio, book-summary-if-not-yet,
// annotations); Y is the whole-book listen estimate independent of toggles.
const deltaSummaryCount = computed(() =>
  Math.max(0, props.totalUnits - props.generatedCount),
)
const deltaBookCount = computed(() => (props.bookSummaryGenerated ? 0 : 1))
const deltaAnnotationsCount = computed(() => Math.max(0, props.totalAnnotations))

const totalUnitsToGenerate = computed(() => {
  let n = 0
  if (includeSummary.value) n += deltaSummaryCount.value
  if (includeBook.value) n += deltaBookCount.value
  if (includeAnnotations.value) n += deltaAnnotationsCount.value
  return n
})

const cost = computed(() => estimateGenerateCost({ totalUnits: totalUnitsToGenerate.value }))

const genMinText = computed(() => {
  const m = cost.value.minutes
  // 1 decimal when fractional, integer otherwise — keeps "0.6" but renders "0" cleanly.
  const formatted = Number.isInteger(m) ? `${m}` : m.toFixed(1)
  return `~${formatted}min to generate`
})

const listenMinText = computed(() => {
  const wpm = settingsStore?.settings?.tts?.listen_wpm ?? 180
  const minutes = props.totalWordCount > 0 && wpm > 0
    ? Math.round(props.totalWordCount / wpm)
    : 0
  return `~${minutes}min to listen`
})

const diskMbText = computed(() => `~${Math.round(cost.value.megabytes)}MB on disk`)

const sectionsToGenerateForSubline = computed(() =>
  includeSummary.value ? deltaSummaryCount.value : 0,
)

const sublineText = computed(
  () => `Generating ${sectionsToGenerateForSubline.value} of ${props.totalUnits} sections`,
)

const buttonLabel = computed(() =>
  totalUnitsToGenerate.value === 0 ? 'Nothing to generate' : 'Generate',
)

const summaryDisabled = computed(() => deltaSummaryCount.value === 0)
const bookDisabled = computed(() => deltaBookCount.value === 0)
const annotationsDisabled = computed(() => deltaAnnotationsCount.value === 0)

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
          <input
            v-model="includeSummary"
            type="checkbox"
            data-testid="include-section-summaries"
            :disabled="summaryDisabled"
          />
          Section summaries
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input
            v-model="includeBook"
            type="checkbox"
            data-testid="include-book-summary"
            :disabled="bookDisabled"
          />
          Book summary
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input
            v-model="includeAnnotations"
            type="checkbox"
            data-testid="include-annotations"
            :disabled="annotationsDisabled"
          />
          Annotations
          <span class="chip chip--warn">
            recommended
          </span>
        </label>
      </fieldset>

      <p class="estimate-row mt-3 text-xs text-slate-500" data-testid="cost-estimate">
        <span data-testid="estimate-generate">{{ genMinText }}</span>
        <span aria-hidden="true"> · </span>
        <span data-testid="estimate-listen">{{ listenMinText }}</span>
        <span aria-hidden="true"> · </span>
        <span data-testid="estimate-disk">{{ diskMbText }}</span>
      </p>
      <p class="estimate-subline text-xs text-slate-500" data-testid="estimate-subline">
        {{ sublineText }}
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
        <button type="button" class="btn-secondary" @click="emit('close')">
          Cancel
        </button>
        <button
          type="button"
          data-testid="confirm"
          class="btn-primary"
          :disabled="submitting || (needsDownload ?? false) || totalUnitsToGenerate === 0"
          @click="onConfirm"
        >
          {{ buttonLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
