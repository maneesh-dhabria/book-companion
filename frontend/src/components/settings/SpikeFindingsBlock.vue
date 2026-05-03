<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { computed, onMounted, ref } from 'vue'

interface SpikeResp {
  available: boolean
  path?: string
  content_md?: string
}

const data = ref<SpikeResp>({ available: false })
const loading = ref(true)
const md = new MarkdownIt({ html: false, linkify: true })

const renderedHtml = computed(() => {
  if (!data.value.content_md) return ''
  return DOMPurify.sanitize(md.render(data.value.content_md))
})

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/spikes/tts')
    if (r.ok) data.value = (await r.json()) as SpikeResp
  } catch {
    /* swallow */
  } finally {
    loading.value = false
  }
}

const SAMPLE_TEXT =
  'The quick brown fox jumps over the lazy dog, and learning never stops.'

async function listenComparison() {
  try {
    const r = await fetch('/api/v1/audio/sample', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ engine: 'kokoro', voice: 'af_sarah', text: SAMPLE_TEXT }),
    })
    if (r.ok) {
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = new Audio(url)
      a.addEventListener('ended', () => URL.revokeObjectURL(url))
      await a.play()
    }
  } catch {
    /* ignore */
  }
  try {
    const u = new SpeechSynthesisUtterance(SAMPLE_TEXT)
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(u)
  } catch {
    /* ignore */
  }
}

onMounted(load)
</script>

<template>
  <section class="spike-findings rounded-md border border-slate-200 p-4">
    <h3 class="mb-2 text-sm font-semibold text-slate-800">Spike findings</h3>
    <div v-if="loading" class="text-sm text-slate-500">Loading…</div>
    <template v-else-if="data.available">
      <!-- markdown content; sanitized via DOMPurify -->
      <div class="prose prose-sm max-w-none" v-html="renderedHtml"></div>
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="listen-comparison"
          class="rounded-md bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500"
          @click="listenComparison"
        >
          Listen to comparison
        </button>
        <a
          v-if="data.path"
          :href="`#${data.path}`"
          class="text-xs text-indigo-600 hover:underline"
          >{{ data.path.split('/').pop() }}</a
        >
      </div>
    </template>
    <p v-else class="text-sm text-slate-600">
      Spike not yet run. Run <code class="rounded bg-slate-100 px-1">bookcompanion spike tts</code>
      to compare engines and capture findings.
    </p>
  </section>
</template>
