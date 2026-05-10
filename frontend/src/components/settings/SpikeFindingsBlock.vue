<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { computed, onMounted, ref } from 'vue'

interface CompareVoicesResp {
  available: boolean
  path?: string
  content_md?: string
}

const props = defineProps<{ bookId?: number }>()

const data = ref<CompareVoicesResp>({ available: false })
const loading = ref(true)
// FR-19: per-component cache for the markdown-stripped section[0] preamble.
const sampleTextCache = ref<string | null>(null)
const md = new MarkdownIt({ html: false, linkify: true })

const renderedHtml = computed(() => {
  if (!data.value.content_md) return ''
  return DOMPurify.sanitize(md.render(data.value.content_md))
})

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/spikes/tts')
    if (r.ok) data.value = (await r.json()) as CompareVoicesResp
  } catch {
    /* swallow */
  } finally {
    loading.value = false
  }
}

const PANGRAM_FALLBACK =
  'The quick brown fox jumps over the lazy dog, and learning never stops.'
const KOKORO_VOICE = 'af_sarah'

// FR-19: lightweight markdown stripper. Removes bold/italic markers, headings,
// inline code, and link wrappers; collapses whitespace. Plain text only.
function stripMarkdown(input: string): string {
  return input
    .replace(/!\[[^\]]*]\([^)]*\)/g, '') // images
    .replace(/\[([^\]]+)]\([^)]*\)/g, '$1') // links → text
    .replace(/`([^`]+)`/g, '$1') // inline code
    .replace(/\*\*([^*]+)\*\*/g, '$1') // bold
    .replace(/\*([^*]+)\*/g, '$1') // italic *
    .replace(/__([^_]+)__/g, '$1') // bold _
    .replace(/_([^_]+)_/g, '$1') // italic _
    .replace(/^#{1,6}\s+/gm, '') // headings
    .replace(/^>\s?/gm, '') // blockquote
    .replace(/\s+/g, ' ')
    .trim()
}

async function resolveSampleText(): Promise<string> {
  if (sampleTextCache.value !== null) return sampleTextCache.value
  if (props.bookId === undefined) {
    sampleTextCache.value = PANGRAM_FALLBACK
    return PANGRAM_FALLBACK
  }
  try {
    const r = await fetch(`/api/v1/books/${props.bookId}`)
    if (!r.ok) throw new Error(`book fetch failed: ${r.status}`)
    const j = (await r.json()) as { sections?: Array<{ content_md?: string }> }
    const md = j.sections?.[0]?.content_md ?? ''
    const stripped = stripMarkdown(md).slice(0, 280)
    const text = stripped.length >= 20 ? stripped : PANGRAM_FALLBACK
    sampleTextCache.value = text
    return text
  } catch {
    sampleTextCache.value = PANGRAM_FALLBACK
    return PANGRAM_FALLBACK
  }
}

// FR-18: transient chip shows which engine is currently playing during the
// A/B comparison. Empty string = chip hidden.
const chipText = ref('')

async function playWebSpeech(text: string) {
  try {
    const u = new SpeechSynthesisUtterance(text)
    u.onend = () => {
      // Clear the chip 1s after Web Speech ends so the user sees the final
      // "Playing Web Speech…" state catch up to silence (FR-18).
      setTimeout(() => {
        chipText.value = ''
      }, 1000)
    }
    chipText.value = 'Playing Web Speech…'
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(u)
  } catch {
    chipText.value = ''
  }
}

async function listenComparison() {
  const sampleText = await resolveSampleText()
  let kokoroPlayed = false
  try {
    const r = await fetch('/api/v1/audio/sample', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ engine: 'kokoro', voice: KOKORO_VOICE, text: sampleText }),
    })
    if (r.ok) {
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = new Audio(url)
      a.addEventListener('ended', () => {
        URL.revokeObjectURL(url)
        void playWebSpeech(sampleText)
      })
      chipText.value = `Playing Kokoro (${KOKORO_VOICE})…`
      kokoroPlayed = true
      await a.play()
    }
  } catch {
    /* fall through to Web Speech */
  }
  if (!kokoroPlayed) {
    // Kokoro unavailable — flip straight to Web Speech.
    void playWebSpeech(sampleText)
  }
}

onMounted(load)
</script>

<template>
  <section class="compare-voices rounded-md border border-slate-200 p-4">
    <h3 class="mb-2 text-sm font-semibold text-slate-800">Compare voices</h3>
    <div v-if="loading" class="text-sm text-slate-500">Loading…</div>
    <template v-else>
      <!-- markdown content (when authored notes are present); sanitized via DOMPurify -->
      <div
        v-if="data.available"
        class="prose prose-sm max-w-none"
        v-html="renderedHtml"
      ></div>
      <p v-else class="text-sm text-slate-600">
        Hear the same sample in both engines below. Click to compare Kokoro and your
        browser's Web Speech voice side by side.
      </p>
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="listen-comparison"
          class="rounded-md bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500"
          @click="listenComparison"
        >
          Listen to comparison
        </button>
        <span
          v-if="chipText"
          class="bc-chip bc-chip--engine"
          data-testid="engine-chip"
          aria-live="polite"
        >
          {{ chipText }}
        </span>
        <a
          v-if="data.available && data.path"
          :href="`#${data.path}`"
          class="text-xs text-indigo-600 hover:underline"
          >{{ data.path.split('/').pop() }}</a
        >
      </div>
    </template>
  </section>
</template>
