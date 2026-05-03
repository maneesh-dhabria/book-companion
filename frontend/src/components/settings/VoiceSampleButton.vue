<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  engine: 'web-speech' | 'kokoro'
  voice: string
  text?: string
}>()

const loading = ref(false)
const error = ref<string | null>(null)

const SAMPLE_TEXT =
  'The quick brown fox jumps over the lazy dog, and learning never stops.'

let currentAudio: HTMLAudioElement | null = null

async function onClick() {
  if (loading.value) return
  error.value = null
  const text = props.text ?? SAMPLE_TEXT

  if (props.engine === 'web-speech') {
    try {
      const u = new SpeechSynthesisUtterance(text)
      const voices = window.speechSynthesis.getVoices()
      const match = voices.find((v) => v.name === props.voice)
      if (match) u.voice = match
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(u)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'sample failed'
    }
    return
  }

  loading.value = true
  try {
    const r = await fetch('/api/v1/audio/sample', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ engine: 'kokoro', voice: props.voice, text }),
    })
    if (!r.ok) throw new Error(`sample failed: ${r.status}`)
    const blob = await r.blob()
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    const url = URL.createObjectURL(blob)
    currentAudio = new Audio(url)
    currentAudio.addEventListener('ended', () => URL.revokeObjectURL(url))
    await currentAudio.play()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'sample failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="voice-sample">
    <button
      type="button"
      :data-testid="`sample-${engine}-${voice}`"
      class="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading"
      @click="onClick"
    >
      <span v-if="loading" data-testid="loading-spinner">Loading…</span>
      <span v-else>Sample</span>
    </button>
    <p v-if="error" class="mt-1 text-xs text-red-600" role="alert">{{ error }}</p>
  </div>
</template>
