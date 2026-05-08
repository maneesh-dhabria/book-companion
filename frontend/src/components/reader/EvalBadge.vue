<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  passed: number
  total: number
}>()

const toneClass = computed(() => {
  if (props.total === 0) return 'chip--neutral'
  const ratio = props.passed / props.total
  if (ratio >= 1) return 'chip--accent'
  if (ratio >= 0.75) return 'chip--warn'
  return 'chip--warn'
})
</script>

<template>
  <span class="eval-badge chip" :class="toneClass">
    {{ passed }}/{{ total }}
  </span>
</template>

<style scoped>
.eval-badge { font-weight: 600; }
</style>
