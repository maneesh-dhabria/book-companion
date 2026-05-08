<script setup lang="ts">
import { computed } from 'vue'

import { useEngineCopy, type EngineReason } from '@/composables/audio/useEngineCopy'

const props = defineProps<{
  engine: 'mp3' | 'web-speech' | 'kokoro' | string
  voice?: string | null
  defaultEngine?: string | null
  reason?: EngineReason | null
}>()

const isKokoro = computed(() => props.engine === 'kokoro' || props.engine === 'mp3')

const label = computed(() => {
  const eng = isKokoro.value ? 'Kokoro' : 'Web Speech'
  return props.voice ? `${eng} · ${props.voice}` : eng
})

const showTooltip = computed(() => {
  if (!props.defaultEngine || !props.reason) return false
  // Show tooltip whenever default differs from active engine label.
  return (props.defaultEngine === 'kokoro' && !isKokoro.value)
    || (props.defaultEngine === 'web-speech' && isKokoro.value)
})

const tooltipText = computed(() => useEngineCopy(props.reason, props.defaultEngine ?? null))
</script>

<template>
  <span
    class="bc-engine-chip chip"
    :class="isKokoro
      ? 'bc-engine-chip--kokoro chip--info'
      : 'bc-engine-chip--web-speech chip--neutral'"
  >
    {{ label }}
    <span v-if="showTooltip" role="tooltip" class="sr-only">{{ tooltipText }}</span>
  </span>
</template>
