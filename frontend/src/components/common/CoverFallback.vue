<template>
  <svg
    role="img"
    :aria-label="`Cover for ${title}`"
    class="cover-fallback"
    :viewBox="`0 0 ${width} ${height}`"
    :width="width"
    :height="height"
    preserveAspectRatio="xMidYMid slice"
  >
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" :stop-color="gradient.from" />
        <stop offset="100%" :stop-color="gradient.to" />
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" :fill="`url(#${gradientId})`" />
    <text
      :x="width / 2"
      :y="height / 2"
      text-anchor="middle"
      dominant-baseline="middle"
      fill="rgba(255,255,255,0.9)"
      :font-size="Math.round(width / 8)"
      font-weight="700"
      :style="{ letterSpacing: '0.02em' }"
    >
      {{ initial }}
    </text>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { coverGradientFor } from '@/utils/coverHash'

const props = withDefaults(
  defineProps<{
    title: string
    width?: number
    height?: number
  }>(),
  { width: 180, height: 270 },
)

const gradient = computed(() => coverGradientFor(props.title))
const gradientId = computed(() => `cf-${gradient.value.id}`)
const initial = computed(() => (props.title?.trim() || '?').charAt(0).toUpperCase())
</script>

<style scoped>
.cover-fallback {
  display: block;
  border-radius: 0.25rem;
}
</style>
