<template>
  <div
    v-if="missedConcepts.length > 0 || partialConcepts.length > 0"
    data-test="warm-up-banner"
    class="warm-up-banner"
    role="status"
  >
    <p v-if="missedConcepts.length > 0">
      Last time you marked
      <strong>{{ formatList(missedConcepts) }}</strong>
      as Missed.
    </p>
    <p v-if="partialConcepts.length > 0">
      Last time you marked
      <strong>{{ formatList(partialConcepts) }}</strong>
      as Partial.
    </p>
    <p class="hint">We'll start with these to consolidate.</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  missedConcepts: string[]
  partialConcepts: string[]
}>()

function formatList(items: string[]): string {
  if (items.length === 0) return ''
  if (items.length === 1) return items[0]
  if (items.length === 2) return `${items[0]} and ${items[1]}`
  return `${items.slice(0, -1).join(', ')}, and ${items[items.length - 1]}`
}
</script>

<style scoped>
.warm-up-banner {
  padding: 0.75rem 1rem;
  background: var(--color-info-bg, #eff6ff);
  color: var(--color-info-text, #1e40af);
  border-left: 3px solid #3b82f6;
  border-radius: 4px;
  margin-bottom: 1rem;
}
.warm-up-banner .hint {
  font-size: 0.85rem;
  opacity: 0.85;
  margin-top: 0.5rem;
  margin-bottom: 0;
}
.warm-up-banner p {
  margin: 0.25rem 0;
}
</style>
