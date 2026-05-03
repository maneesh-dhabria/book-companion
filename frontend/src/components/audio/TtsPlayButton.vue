<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import type { AudioLookupResponse } from '@/api/audio'
import * as preloadCache from '@/composables/audio/preloadCache'
import type { PreloadContentType } from '@/composables/audio/preloadCache'
import { useTtsEngine } from '@/composables/audio/useTtsEngine'
import { useWebSpeechSupported } from '@/composables/useWebSpeechSupported'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const props = defineProps<{
  contentType: PreloadContentType
  contentId: number
  hasSummary?: boolean
  bookId?: number
}>()

const store = useTtsPlayerStore()
const engine = useTtsEngine()
const { supported: webSpeechSupported } = useWebSpeechSupported()

const buttonEl = ref<HTMLButtonElement | null>(null)
const preloadResult = ref<AudioLookupResponse | null>(null)
const preloadFailed = ref(false)
const loadingClick = ref(false)
// Tri-state visibility while we resolve preload (FR-25g): 'hidden-while-resolving'
// renders the button with `visibility: hidden` so layout is reserved but it's
// not interactive; 'visible' shows it; 'gone' removes from layout.
const resolveState = ref<'hidden-while-resolving' | 'visible' | 'gone'>(
  'hidden-while-resolving',
)
let observer: IntersectionObserver | null = null
let fallbackTimer: number | null = null

const visibilityComputed = computed(() => {
  if (props.hasSummary === false) return 'gone'
  const r = preloadResult.value
  if (r === null && !preloadFailed.value) return resolveState.value
  if (r && r.sanitized_text === '') return 'gone'
  if (webSpeechSupported.value) return 'visible'
  if (r?.pregenerated) return 'visible'
  return 'gone'
})

const inlineStyle = computed(() => {
  const v = visibilityComputed.value
  if (v === 'gone') return { display: 'none' }
  if (v === 'hidden-while-resolving') return { visibility: 'hidden' as const }
  return {}
})

const disabled = computed(
  () => loadingClick.value || props.hasSummary === false,
)

async function triggerPreload(): Promise<void> {
  if (props.hasSummary === false) return
  try {
    const result = await preloadCache.preload({
      bookId: props.bookId ?? 0,
      contentType: props.contentType,
      contentId: props.contentId,
    })
    preloadResult.value = result
    resolveState.value = 'visible'
  } catch {
    preloadFailed.value = true
    resolveState.value = webSpeechSupported.value ? 'visible' : 'gone'
  }
}

async function onClick(): Promise<void> {
  if (visibilityComputed.value === 'gone') return
  loadingClick.value = true
  try {
    if (props.contentType !== 'annotation') {
      store.open({
        contentType: props.contentType,
        contentId: props.contentId,
      })
    }
    if (props.contentType !== 'annotation') {
      await engine.load({
        bookId: props.bookId ?? 0,
        contentType: props.contentType,
        contentId: props.contentId,
      })
    } else {
      // Annotation playback: preload the lookup so on-screen Web Speech can
      // pick it up via the cache (cache is the gesture-preserving fast
      // path). Engine wiring for single-annotation playback ships in a
      // follow-up — for today, ensure the preload runs.
      await preloadCache.preload({
        bookId: props.bookId ?? 0,
        contentType: 'annotation',
        contentId: props.contentId,
      })
    }
  } finally {
    loadingClick.value = false
  }
}

onMounted(() => {
  const el = buttonEl.value
  if (props.contentType === 'section_content') {
    // FR-25a / G1: hover/focus/touchstart preload for large content.
    if (el) {
      const trigger = () => {
        el.removeEventListener('mouseenter', trigger)
        el.removeEventListener('focus', trigger)
        el.removeEventListener('touchstart', trigger)
        void triggerPreload()
      }
      el.addEventListener('mouseenter', trigger, { once: true })
      el.addEventListener('focus', trigger, { once: true })
      el.addEventListener('touchstart', trigger, { once: true, passive: true })
    }
  } else if (typeof IntersectionObserver !== 'undefined' && el) {
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          observer?.disconnect()
          window.setTimeout(() => void triggerPreload(), 500)
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(el)
  }
  fallbackTimer = window.setTimeout(() => {
    if (resolveState.value === 'hidden-while-resolving') {
      resolveState.value = webSpeechSupported.value ? 'visible' : 'gone'
    }
  }, 300)
})

onUnmounted(() => {
  observer?.disconnect()
  if (fallbackTimer !== null) window.clearTimeout(fallbackTimer)
})

defineExpose({ _triggerPreloadForTests: triggerPreload })
</script>

<template>
  <button
    ref="buttonEl"
    type="button"
    class="btn-secondary tts-play-button"
    :style="inlineStyle"
    :disabled="disabled || undefined"
    :aria-disabled="disabled ? 'true' : undefined"
    :title="
      props.hasSummary === false
        ? 'Audio is only generated for summaries'
        : 'Listen'
    "
    @click="onClick"
  >
    <svg
      v-if="!loadingClick"
      class="h-4 w-4"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M6 4l10 6-10 6V4z" />
    </svg>
    <svg
      v-else
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
    <span>Listen</span>
  </button>
</template>

<style scoped>
.tts-play-button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}
</style>
