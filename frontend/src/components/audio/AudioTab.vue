<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { audioApi, type AudioInventoryItem } from '@/api/audio'
import DifferencePopover from '@/components/audio/DifferencePopover.vue'
import EngineChip from '@/components/audio/EngineChip.vue'
import EnginePicker from '@/components/audio/EnginePicker.vue'
import GenerateAudioModal from '@/components/audio/GenerateAudioModal.vue'
import { useAudioJobStore } from '@/stores/audioJob'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const props = defineProps<{ bookId: number }>()

const showGenerateModal = ref(false)
const showDiff = ref(false)
const ttsPlayer = useTtsPlayerStore()

// FR-08 / D10: Web Speech voices populate asynchronously on Safari/Chrome.
// Race the `voiceschanged` event vs a 500ms timeout so first-paint isn't
// blocked indefinitely. `availableVoices` is recomputed when ready so
// downstream gates (FR-09 listen-unavailable morph, voice selector) can
// inspect the live list.
const voicesReady = ref(false)
const availableVoices = ref<SpeechSynthesisVoice[]>([])

function refreshVoices(): void {
  const synth = window.speechSynthesis
  if (!synth) return
  availableVoices.value = synth.getVoices() ?? []
}

onMounted(() => {
  const synth = window.speechSynthesis
  if (!synth) {
    // FR-09: no Web Speech at all — voicesReady still flips so downstream
    // computeds can decide what to render (the unavailable morph reads
    // 'speechSynthesis' in window directly).
    voicesReady.value = true
    return
  }
  refreshVoices()
  if (availableVoices.value.length > 0) {
    voicesReady.value = true
    return
  }
  let resolved = false
  const finish = () => {
    if (resolved) return
    resolved = true
    refreshVoices()
    voicesReady.value = true
  }
  synth.addEventListener('voiceschanged', finish, { once: true })
  setTimeout(finish, 500)
})

// Default engine label/string. Defaults to 'web-speech' when no setting
// has been pulled yet — the Settings TTS panel populates this on mount.
const defaultEngine = computed<'kokoro' | 'web-speech'>(() =>
  ttsPlayer.defaultEngine === 'mp3' ? 'kokoro' : 'web-speech',
)

// FR-09: Listen is unavailable when the browser has no speechSynthesis at
// all, OR when voicesReady has settled and getVoices() came back empty
// (private mode / hardened profiles can disable voices without nulling
// the API). The morph also covers REVIEW-LOG #2 — the sr-only tip is
// always rendered, not conditionally injected after the fact.
const listenAvailable = computed<boolean>(() => {
  if (typeof window === 'undefined') return true
  if (!('speechSynthesis' in window)) return false
  if (!voicesReady.value) return true
  return availableVoices.value.length > 0
})
const audioEmptyHeading = computed(() =>
  listenAvailable.value ? 'Listen to this book' : 'Generate MP3s to listen to this book',
)

// FR-11: populated state default — pre-generated MP3s exist → start in 'mp3'
// to honour the user's prior generation work. Otherwise stay on 'web-speech'.
const populatedEngine = ref<'mp3' | 'web-speech'>('web-speech')
function syncDefaultEngine() {
  populatedEngine.value = coverage.value.generated >= 1 ? 'mp3' : 'web-speech'
}
function onEngineChange(kind: 'mp3' | 'web-speech') {
  populatedEngine.value = kind
  ttsPlayer.setEngine?.(kind)
}

// Generation estimate copy: ~30s per content unit on Kokoro; instant on
// Web Speech (no pre-generation).
const estimateCopy = computed(() => {
  if (defaultEngine.value === 'web-speech') {
    return 'Instant on Web Speech (no pre-generation needed)'
  }
  const totalUnits = coverage.value.total
  const seconds = totalUnits * 30
  const minutes = Math.max(1, Math.round(seconds / 60))
  return `≈ ${minutes} min on Kokoro`
})

const scopeCopy = computed(() => {
  const n = coverage.value.total
  return `${n} chapter ${n === 1 ? 'summary' : 'summaries'}`
})

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
    syncDefaultEngine()
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
    const r = await fetch(`/api/v1/jobs/${id}/cancel`, { method: 'POST' })
    if (!r.ok) return
    jobStore?.clear()
  } catch {
    /* toast handled elsewhere */
  }
}

function onGenerate() {
  showGenerateModal.value = true
}

function onListen() {
  // FR-10: kick off Web Speech playback for the empty-state book. Wired in T17/T18
  // when the engine picker / play-section pipeline lands; for now this is a hook
  // that engine-aware tests can spy on without coupling to ttsPlayer's full API.
  if (!listenAvailable.value) return
  ttsPlayer.startBookListen?.(props.bookId)
}

function onModalClose() {
  showGenerateModal.value = false
}

onMounted(load)

// Test seam — keep voicesReady accessible to mount-based pre-warm tests.
defineExpose({ voicesReady, availableVoices })
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
        class="btn-secondary"
        @click="onCancelJob"
      >
        Cancel
      </button>
    </div>

    <div v-else-if="state === 'no-audio'" data-testid="state-no-audio" class="audio-empty">
      <div class="flex items-center gap-2">
        <EngineChip :engine="defaultEngine" />
      </div>
      <h2 data-testid="audio-empty-heading" class="audio-empty-heading">
        {{ audioEmptyHeading }}
      </h2>
      <p data-testid="audio-empty-subtitle" class="text-sm text-slate-700 dark:text-slate-200">
        Instant playback via your browser, or generate MP3s for offline listening.
      </p>
      <p data-testid="audio-estimate" class="text-xs text-slate-500 dark:text-slate-400">
        {{ estimateCopy }} · <span data-testid="audio-scope">{{ scopeCopy }}</span>
      </p>
      <div class="mt-2 flex flex-wrap items-center gap-3 audio-empty-actions">
        <button
          type="button"
          data-testid="listen-cta"
          class="btn-primary"
          :disabled="!listenAvailable"
          aria-describedby="listen-tip"
          @click="onListen"
        >
          Listen
        </button>
        <span id="listen-tip" class="sr-only">
          Web Speech is unavailable in this browser. Generate MP3 files instead.
        </span>
        <button
          type="button"
          data-testid="generate-cta"
          class="btn-secondary"
          @click="onGenerate"
        >
          Generate MP3 files
        </button>
        <button
          type="button"
          data-testid="diff-trigger"
          class="text-sm text-indigo-600 underline"
          @click.stop="showDiff = !showDiff"
        >
          What's the difference?
        </button>
        <DifferencePopover :open="showDiff" @close="showDiff = false" />
      </div>
      <p data-testid="audio-empty-caption" class="text-slate-500 text-sm">
        No audio files yet — generate to enable seek/scrub.
      </p>
    </div>

    <div v-else-if="state === 'partial'" data-testid="state-partial">
      <div
        data-testid="audio-engine-row"
        class="flex flex-wrap items-center gap-3 audio-engine-row"
      >
        <EnginePicker
          :model-value="populatedEngine"
          @update:model-value="onEngineChange"
        />
      </div>
      <p class="text-sm text-slate-700 mt-2">
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
      <div
        data-testid="audio-engine-row"
        class="flex flex-wrap items-center gap-3 audio-engine-row"
      >
        <EnginePicker
          :model-value="populatedEngine"
          @update:model-value="onEngineChange"
        />
      </div>
      <p class="text-sm text-slate-700 mt-2">
        All {{ coverage.total }} sections have audio.
      </p>
    </div>

    <GenerateAudioModal
      v-if="showGenerateModal"
      :open="showGenerateModal"
      :book-id="bookId"
      :total-units="coverage.total"
      :total-annotations="0"
      @close="onModalClose"
    />
  </div>
</template>

<style scoped>
.audio-empty {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.audio-empty-actions {
  position: relative;
}
.audio-empty-heading {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text, #0f172a);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
