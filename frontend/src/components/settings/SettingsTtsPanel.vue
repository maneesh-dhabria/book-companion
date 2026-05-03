<script setup lang="ts">
import { onMounted, ref } from 'vue'

import KokoroStatusIndicator from '@/components/settings/KokoroStatusIndicator.vue'
import SpikeFindingsBlock from '@/components/settings/SpikeFindingsBlock.vue'
import VoiceSampleButton from '@/components/settings/VoiceSampleButton.vue'

type Engine = 'web-speech' | 'kokoro'

const KOKORO_VOICE_OPTIONS = ['af_sarah', 'af_bella', 'af_nicole', 'am_adam', 'am_echo', 'bf_emma']

const engine = ref<Engine>('web-speech')
const kokoroVoice = ref('af_sarah')
const webSpeechVoice = ref('Samantha')
const defaultSpeed = ref(1.0)
const autoAdvance = ref(true)
const webSpeechVoices = ref<string[]>([])
const saving = ref(false)
const savedAt = ref<number | null>(null)
const error = ref<string | null>(null)
const noVoicesAvailable = ref(false)

async function load() {
  try {
    const r = await fetch('/api/v1/settings/tts')
    if (!r.ok) throw new Error(`load failed: ${r.status}`)
    const j = await r.json()
    engine.value = (j.engine as Engine) ?? 'web-speech'
    if (j.engine === 'kokoro') {
      kokoroVoice.value = j.voice ?? 'af_sarah'
    } else if (j.voice) {
      webSpeechVoice.value = j.voice
    }
    defaultSpeed.value = j.default_speed ?? 1.0
    autoAdvance.value = j.auto_advance ?? true
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'load failed'
  }
}

function loadWebSpeechVoices() {
  try {
    const voices = window.speechSynthesis?.getVoices?.() ?? []
    webSpeechVoices.value = voices.map((v) => v.name)
    noVoicesAvailable.value = voices.length === 0
  } catch {
    noVoicesAvailable.value = true
  }
}

async function onSave() {
  saving.value = true
  error.value = null
  try {
    const voice = engine.value === 'kokoro' ? kokoroVoice.value : webSpeechVoice.value
    const r = await fetch('/api/v1/settings/tts', {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        engine: engine.value,
        voice,
        default_speed: defaultSpeed.value,
        auto_advance: autoAdvance.value,
      }),
    })
    if (!r.ok) {
      const text = await r.text().catch(() => '')
      throw new Error(`save failed: ${r.status} ${text}`)
    }
    savedAt.value = Date.now()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'save failed'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
  loadWebSpeechVoices()
  if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = loadWebSpeechVoices
  }
})
</script>

<template>
  <section class="settings-tts space-y-6" data-testid="settings-tts-panel">
    <header>
      <h2 class="text-lg font-semibold text-slate-800">Text-to-speech</h2>
      <p class="text-sm text-slate-500">
        Choose an engine and voice for audiobook playback.
      </p>
    </header>

    <SpikeFindingsBlock />

    <fieldset class="space-y-3 rounded-md border border-slate-200 p-4">
      <legend class="px-1 text-sm font-medium text-slate-700">Engine</legend>

      <label class="flex items-start gap-3">
        <input
          type="radio"
          name="tts-engine"
          value="web-speech"
          :checked="engine === 'web-speech'"
          class="mt-1"
          @change="engine = 'web-speech'"
        />
        <div class="flex-1">
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-medium text-slate-800">Web Speech (browser)</span>
            <VoiceSampleButton engine="web-speech" :voice="webSpeechVoice" />
          </div>
          <p class="text-xs text-slate-500">Free; uses your browser's built-in voices.</p>
          <div class="mt-2 flex items-center gap-2">
            <label class="text-xs text-slate-500">Voice</label>
            <select
              v-model="webSpeechVoice"
              class="rounded border border-slate-300 px-2 py-1 text-sm"
              :disabled="engine !== 'web-speech'"
            >
              <option v-if="noVoicesAvailable" value="" disabled>No voices available</option>
              <option v-for="v in webSpeechVoices" :key="v" :value="v">{{ v }}</option>
            </select>
          </div>
        </div>
      </label>

      <label class="flex items-start gap-3">
        <input
          type="radio"
          name="tts-engine"
          value="kokoro"
          :checked="engine === 'kokoro'"
          class="mt-1"
          @change="engine = 'kokoro'"
        />
        <div class="flex-1">
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-medium text-slate-800">Kokoro (local, higher quality)</span>
            <VoiceSampleButton engine="kokoro" :voice="kokoroVoice" />
          </div>
          <p class="text-xs text-slate-500">Runs on this device; requires ffmpeg.</p>
          <div class="mt-2 flex items-center gap-2">
            <label class="text-xs text-slate-500">Voice</label>
            <select
              v-model="kokoroVoice"
              class="rounded border border-slate-300 px-2 py-1 text-sm"
              :disabled="engine !== 'kokoro'"
            >
              <option v-for="v in KOKORO_VOICE_OPTIONS" :key="v" :value="v">{{ v }}</option>
            </select>
          </div>
          <div class="mt-2">
            <KokoroStatusIndicator />
          </div>
        </div>
      </label>
    </fieldset>

    <fieldset class="space-y-3 rounded-md border border-slate-200 p-4">
      <legend class="px-1 text-sm font-medium text-slate-700">Playback</legend>
      <label class="flex items-center gap-3 text-sm text-slate-700">
        <span>Default speed</span>
        <input
          v-model.number="defaultSpeed"
          type="range"
          min="0.5"
          max="2"
          step="0.05"
          data-testid="default-speed"
        />
        <span class="text-xs text-slate-500">{{ defaultSpeed.toFixed(2) }}×</span>
      </label>
      <label class="flex items-center gap-3 text-sm text-slate-700">
        <input v-model="autoAdvance" type="checkbox" data-testid="auto-advance" />
        <span>Auto-advance to next section</span>
      </label>
    </fieldset>

    <div class="flex items-center gap-3">
      <button
        type="button"
        data-testid="save"
        class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
        :disabled="saving"
        @click="onSave"
      >
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
      <span v-if="savedAt" class="text-xs text-emerald-600" data-testid="saved-indicator"
        >Saved.</span
      >
      <span v-if="error" class="text-xs text-red-600" role="alert">{{ error }}</span>
    </div>
  </section>
</template>
