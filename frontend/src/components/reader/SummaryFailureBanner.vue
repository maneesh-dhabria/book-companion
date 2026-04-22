<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  failureType: string | null
  message: string | null
  attemptedAt: string | null
  preset?: string | null
}>()

defineEmits<{ retry: [] }>()

const LABELS: Record<string, string> = {
  cli_nonzero_exit: 'CLI exited with an error',
  cli_timeout: 'CLI timed out',
  cli_not_found: 'CLI binary not found',
  schema_parse_failed: 'LLM response did not match the expected schema',
  empty_output: 'LLM returned an empty summary',
  summarization_error: 'Summarization error',
  unknown: 'Unknown error',
}

const humanType = computed(() =>
  props.failureType ? LABELS[props.failureType] || props.failureType : null,
)
const attemptedLabel = computed(() => {
  if (!props.attemptedAt) return null
  try {
    const d = new Date(props.attemptedAt)
    if (Number.isNaN(d.getTime())) return props.attemptedAt
    return d.toLocaleString()
  } catch {
    return props.attemptedAt
  }
})
</script>

<template>
  <div class="failure-banner" role="alert" data-testid="summary-failure-banner">
    <div class="heading">
      <strong>Summary failed</strong>
      <span v-if="humanType" class="type">— {{ humanType }}</span>
    </div>
    <p v-if="message" class="message">{{ message }}</p>
    <p v-if="attemptedLabel || preset" class="meta">
      <span v-if="attemptedLabel">Last attempt: {{ attemptedLabel }}</span>
      <span v-if="preset"> · Preset: {{ preset }}</span>
    </p>
    <div class="actions">
      <button
        type="button"
        class="retry-btn"
        data-testid="retry-btn"
        @click="$emit('retry')"
      >
        Retry
      </button>
    </div>
  </div>
</template>

<style scoped>
.failure-banner {
  border: 1px solid var(--color-danger, #b91c1c);
  background: var(--color-danger-light, #fef2f2);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  color: var(--color-text-primary, #111);
}
.heading { font-size: 1rem; }
.type { color: var(--color-danger, #b91c1c); font-weight: 500; margin-left: 0.25rem; }
.message { margin: 0; font-size: 0.9rem; }
.meta { margin: 0; font-size: 0.8rem; opacity: 0.75; }
.actions { display: flex; justify-content: flex-end; }
.retry-btn {
  padding: 0.4rem 0.9rem;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}
</style>
