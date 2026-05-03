<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

type Status = 'warm' | 'cold' | 'not_downloaded' | 'download_failed' | 'n/a'

const status = ref<Status>('cold')
const downloading = ref(false)
const error = ref<string | null>(null)
let timer: number | null = null

const LABELS: Record<Status, string> = {
  warm: 'Kokoro: warm',
  cold: 'Kokoro: cold',
  not_downloaded: 'Model not downloaded',
  download_failed: 'Download failed',
  'n/a': 'Kokoro disabled',
}

async function poll() {
  try {
    const r = await fetch('/api/v1/settings/tts/status')
    if (!r.ok) throw new Error(`status ${r.status}`)
    const j = await r.json()
    status.value = (j.status as Status) ?? 'cold'
  } catch {
    /* ignore transient */
  }
}

async function onDownload() {
  if (downloading.value) return
  downloading.value = true
  error.value = null
  try {
    const r = await fetch('/api/v1/settings/tts/download', { method: 'POST' })
    if (!r.ok) throw new Error(`download failed: ${r.status}`)
    await poll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'download failed'
    status.value = 'download_failed'
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  void poll()
  timer = window.setInterval(poll, 10000)
})
onBeforeUnmount(() => {
  if (timer !== null) window.clearInterval(timer)
})
</script>

<template>
  <div class="kokoro-status flex flex-wrap items-center gap-2 text-sm">
    <span :data-status="status" class="inline-flex items-center gap-1.5">
      <span
        v-if="status === 'warm'"
        class="inline-block h-2 w-2 rounded-full bg-emerald-500"
        aria-hidden="true"
      />
      <span
        v-else-if="status === 'cold'"
        class="inline-block h-2 w-2 rounded-full bg-slate-400"
        aria-hidden="true"
      />
      <span
        v-else
        class="inline-block h-2 w-2 rounded-full bg-amber-500"
        aria-hidden="true"
      />
      <span class="text-slate-700">{{ LABELS[status] }}</span>
    </span>
    <button
      v-if="status === 'not_downloaded'"
      type="button"
      data-testid="download-model"
      class="rounded-md bg-indigo-600 px-2.5 py-1 text-xs text-white hover:bg-indigo-500 disabled:opacity-50"
      :disabled="downloading"
      @click="onDownload"
    >
      {{ downloading ? 'Downloading…' : 'Download model' }}
    </button>
    <button
      v-if="status === 'download_failed'"
      type="button"
      data-testid="retry-download"
      class="rounded-md border border-amber-300 px-2.5 py-1 text-xs text-amber-700 hover:bg-amber-50"
      :disabled="downloading"
      @click="onDownload"
    >
      Retry download
    </button>
    <p v-if="error" class="text-xs text-red-600" role="alert">{{ error }}</p>
  </div>
</template>
