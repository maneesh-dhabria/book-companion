<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface StaleBook {
  id: number
  title: string
}

const books = ref<StaleBook[]>([])
const dismissed = ref(false)
const queueing = ref(false)
const error = ref<string | null>(null)

const COOKIE = 'bc_stale_audio_banner_dismissed'

function readCookie(): boolean {
  if (typeof document === 'undefined') return false
  return document.cookie.split(';').some((c) => c.trim().startsWith(`${COOKIE}=`))
}

function setDismissCookie() {
  // 24h
  const exp = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString()
  document.cookie = `${COOKIE}=1; expires=${exp}; path=/; SameSite=Lax`
}

const visible = computed(() => books.value.length >= 2 && !dismissed.value)

async function load() {
  if (readCookie()) {
    dismissed.value = true
    return
  }
  try {
    const r = await fetch('/api/v1/audio/stale-books')
    if (!r.ok) return
    const j = await r.json()
    books.value = (j.books as StaleBook[]) ?? []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'load failed'
  }
}

async function regenerateAll() {
  if (queueing.value) return
  queueing.value = true
  error.value = null
  try {
    for (const b of books.value) {
      await fetch(`/api/v1/books/${b.id}/audio`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ scope: 'all', voice: 'af_sarah', engine: 'kokoro' }),
      })
    }
    dismissed.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'queue failed'
  } finally {
    queueing.value = false
  }
}

function onDismiss() {
  setDismissCookie()
  dismissed.value = true
}

onMounted(load)
</script>

<template>
  <div
    v-if="visible"
    class="bc-banner bc-banner--info mb-4 flex flex-wrap items-center gap-3 rounded-md border border-indigo-200 bg-indigo-50 px-4 py-3 text-indigo-900"
    role="status"
    data-testid="stale-audio-banner"
  >
    <p class="flex-1 text-sm">
      <strong>{{ books.length }}</strong> books have stale audio after a recent update.
    </p>
    <button
      type="button"
      data-testid="regenerate-all"
      class="rounded-md bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50"
      :disabled="queueing"
      @click="regenerateAll"
    >
      {{ queueing ? 'Queueing…' : 'Regenerate all' }}
    </button>
    <button
      type="button"
      data-testid="dismiss"
      class="text-xs text-indigo-700 underline hover:no-underline"
      @click="onDismiss"
    >
      Dismiss
    </button>
    <p v-if="error" class="w-full text-xs text-red-600" role="alert">{{ error }}</p>
  </div>
</template>
