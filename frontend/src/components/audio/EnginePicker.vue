<template>
  <div role="radiogroup" aria-label="TTS engine" class="engine-picker">
    <button
      type="button"
      role="radio"
      class="engine-segment"
      :class="{ active: modelValue === 'web-speech' }"
      :aria-checked="modelValue === 'web-speech'"
      data-engine="web-speech"
      @click="select('web-speech')"
    >
      Web Speech
    </button>
    <button
      type="button"
      role="radio"
      class="engine-segment"
      :class="{ active: modelValue === 'mp3' }"
      :aria-checked="modelValue === 'mp3'"
      data-engine="mp3"
      @click="select('mp3')"
    >
      MP3
    </button>
  </div>
</template>

<script setup lang="ts">
import type { TtsEngineKind } from '@/stores/ttsPlayer'

const props = defineProps<{ modelValue: TtsEngineKind }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: TtsEngineKind): void }>()

function select(kind: TtsEngineKind) {
  if (kind === props.modelValue) return
  emit('update:modelValue', kind)
}
</script>

<style scoped>
.engine-picker {
  display: inline-flex;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  overflow: hidden;
}
.engine-segment {
  padding: 0.35rem 0.85rem;
  background: white;
  border: 0;
  border-right: 1px solid #cbd5e1;
  font-size: 0.85rem;
  cursor: pointer;
  color: #334155;
}
.engine-segment:last-child {
  border-right: 0;
}
.engine-segment.active {
  background: #4f46e5;
  color: white;
}
</style>
