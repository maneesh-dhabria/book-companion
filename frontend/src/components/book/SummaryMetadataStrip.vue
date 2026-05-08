<script setup lang="ts">
import { computed } from 'vue'
import { formatDate } from '@/utils/formatDate'

const props = defineProps<{
  preset?: string | null
  generatedAt?: string | null
  evalPassed?: number | null
  evalTotal?: number | null
}>()

const generatedLabel = computed(() => {
  if (!props.generatedAt) return ''
  return formatDate(props.generatedAt)
})

const evalLabel = computed(() => {
  if (props.evalTotal == null || props.evalTotal === 0) return ''
  const passed = props.evalPassed ?? 0
  const pct = Math.round((passed / props.evalTotal) * 100)
  return `${passed}/${props.evalTotal} (${pct}%)`
})
</script>

<template>
  <div class="summary-meta-strip">
    <span v-if="preset" class="meta-cell"
      ><span class="meta-label">Preset:</span> {{ preset }}</span
    >
    <span v-if="generatedLabel" class="meta-cell"
      ><span class="meta-label">Generated:</span> {{ generatedLabel }}</span
    >
    <span v-if="evalLabel" class="meta-cell"
      ><span class="meta-label">Eval:</span> {{ evalLabel }}</span
    >
  </div>
</template>

<style scoped>
.summary-meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.25rem;
  font-size: 0.8rem;
  color: var(--color-text-secondary, #475569);
  border-bottom: 1px solid var(--color-border, #e5e7eb);
  padding: 0 0 0.5rem 0;
  margin: 0 0 0.75rem 0;
}

.meta-label {
  font-weight: 500;
  color: var(--color-text-muted, #64748b);
  margin-right: 0.25rem;
}
</style>
