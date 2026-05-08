<script setup lang="ts">
import { computed } from 'vue'

import EngineChip from '@/components/audio/EngineChip.vue'
import SentenceProgressBar from '@/components/audio/SentenceProgressBar.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const store = useTtsPlayerStore()

const currentTime = computed(() => {
  const offsets = store.sentenceOffsets
  if (!offsets || offsets.length === 0) return 0
  const idx = Math.min(store.sentenceIndex, offsets.length - 1)
  return offsets[idx] ?? 0
})

const totalSeconds = computed(() => {
  const offsets = store.sentenceOffsets
  if (!offsets || offsets.length === 0) return 0
  return offsets[offsets.length - 1] ?? 0
})

function formatTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  const total = Math.floor(s)
  const m = Math.floor(total / 60)
  const sec = total % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function onPlayPause() {
  if (store.status === 'starting') return
  if (store.status === 'playing') {
    store.pause()
  } else {
    store.play()
  }
}

function onPrev() {
  store.prevSentence()
}

function onNext() {
  store.nextSentence()
}

function onClose() {
  store.close()
}

function onRetry() {
  store.retry()
}
</script>

<template>
  <div
    v-if="store.isActive"
    class="bc-playbar fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex flex-col gap-1 rounded-2xl bg-white px-4 py-3 shadow-xl ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700"
    role="region"
    aria-label="Audio player"
  >
    <SentenceProgressBar
      v-if="store.totalSentences > 0 && store.status !== 'error'"
      :total-sentences="store.totalSentences"
      :current-index="store.sentenceIndex"
    />
    <div class="bc-playbar-row flex items-center gap-3">
    <div
      v-if="store.pendingRegenBanner && (store.status === 'paused' || store.status === 'idle' || store.status === 'ended')"
      data-testid="mid-listen-regen"
      class="absolute -top-12 left-0 right-0 rounded-md bg-amber-100 px-3 py-2 text-xs text-amber-900"
    >
      Summary updated since this audio was generated — regenerate to apply.
    </div>
    <template v-if="store.status === 'error'">
      <span
        data-testid="audio-error-message"
        class="text-sm text-red-600 dark:text-red-400"
        :title="`errorKind: ${store.errorKind ?? 'unknown'}`"
      >
        Audio couldn't start. Try again or check your settings.
      </span>
      <button
        data-testid="retry"
        type="button"
        class="btn-primary"
        @click="onRetry"
      >
        Retry
      </button>
    </template>
    <template v-else>
      <button
        type="button"
        class="btn-secondary btn-icon"
        :aria-label="'Previous sentence'"
        @click="onPrev"
      >
        ⏮
      </button>
      <button
        type="button"
        data-testid="play-pause"
        class="btn-primary btn-icon"
        :aria-label="
          store.status === 'starting'
            ? 'Starting'
            : store.status === 'playing'
              ? 'Pause'
              : 'Play'
        "
        :disabled="store.status === 'starting' || undefined"
        :aria-disabled="store.status === 'starting' ? 'true' : undefined"
        @click="onPlayPause"
      >
        <svg
          v-if="store.status === 'starting'"
          class="h-4 w-4 animate-spin"
          viewBox="0 0 20 20"
          aria-hidden="true"
        >
          <circle
            cx="10"
            cy="10"
            r="8"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-dasharray="40"
          />
        </svg>
        <template v-else>
          {{ store.status === 'playing' ? '⏸' : '▶' }}
        </template>
      </button>
      <button
        type="button"
        class="btn-secondary btn-icon"
        aria-label="Next sentence"
        @click="onNext"
      >
        ⏭
      </button>

      <EngineChip
        v-if="store.engine"
        :engine="store.engine"
        :voice="store.voice"
        :default-engine="store.defaultEngine"
        :reason="store.activeEngineReason"
      />

      <span
        v-if="store.engine === 'web-speech'"
        class="limited-wrap"
        tabindex="0"
      >
        <span
          data-testid="limited-controls"
          class="chip chip--warn"
        >
          Limited controls
        </span>
        <span
          data-testid="limited-controls-tooltip"
          role="tooltip"
          class="limited-tooltip"
        >
          Web Speech can't seek/scrub. <a href="/settings/tts#audio">Install Kokoro for full controls →</a>
        </span>
      </span>

      <span class="text-sm text-slate-600 dark:text-slate-300">
        sentence {{ store.sentenceIndex + 1 }} of {{ store.totalSentences }}
      </span>
      <span
        v-if="store.engine !== 'web-speech'"
        data-testid="timestamp"
        class="text-sm text-slate-500 dark:text-slate-400"
      >
        {{ formatTime(currentTime) }} / {{ formatTime(totalSeconds) }}
      </span>

      <button
        type="button"
        class="btn-secondary btn-icon ml-2"
        aria-label="Close player"
        @click="onClose"
      >
        ✕
      </button>
    </template>
    </div>
  </div>
</template>

<style scoped>
.limited-wrap {
  position: relative;
  display: inline-flex;
}
.limited-tooltip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: rgb(15 23 42);
  color: rgb(241 245 249);
  font-size: 0.75rem;
  padding: 0.375rem 0.625rem;
  border-radius: 0.375rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.1s ease-in;
  z-index: 50;
}
.limited-wrap:hover .limited-tooltip,
.limited-wrap:focus-within .limited-tooltip {
  opacity: 1;
  pointer-events: auto;
}
.limited-tooltip a {
  color: rgb(165 180 252);
  text-decoration: underline;
}
</style>
