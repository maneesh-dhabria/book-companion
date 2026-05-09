<template>
  <div data-test="budget-bar" class="budget-bar" :data-state="colorState" role="progressbar"
    :aria-valuenow="usedTokens" :aria-valuemax="maxTokens">
    <div class="bar" :style="{ width: pct + '%' }" />
    <span class="label">{{ usedTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }} tokens</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  usedTokens: number
  maxTokens: number
  /** Set true while the user is attempting to add a chapter that would overflow. */
  attemptedOverflow?: boolean
}>()

const pct = computed(() => Math.min(100, Math.round((props.usedTokens / props.maxTokens) * 100)))
const colorState = computed<'indigo' | 'amber' | 'red'>(() => {
  if (props.attemptedOverflow) return 'red'
  if (pct.value >= 80) return 'amber'
  return 'indigo'
})
</script>

<style scoped>
.budget-bar {
  position: relative;
  height: 24px;
  background: var(--color-bg-muted, #f0f0f0);
  border-radius: 4px;
  overflow: hidden;
  margin: 0.5rem 0;
}
.budget-bar .bar {
  height: 100%;
  transition: width 120ms ease;
}
.budget-bar[data-state='indigo'] .bar {
  background: #4f46e5;
}
.budget-bar[data-state='amber'] .bar {
  background: #f59e0b;
}
.budget-bar[data-state='red'] .bar {
  background: #ef4444;
}
.budget-bar .label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  color: var(--color-text, #111);
}
</style>
