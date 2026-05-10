<template>
  <div
    v-if="diag"
    class="inline-diagnostic"
    data-testid="inline-diagnostic"
    data-state="recovered"
    role="status"
  >
    <p class="inline-diagnostic-reason">{{ diag.reason }}</p>
    <details v-if="diag.stderrTail" class="inline-diagnostic-details">
      <summary>Show details</summary>
      <pre>{{ diag.stderrTail }}</pre>
    </details>
    <button type="button" class="bc-link" @click="$emit('dismiss')">Dismiss</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  diag: { reason: string; stderrTail: string | null } | null
}>()
defineEmits<{ (e: 'dismiss'): void }>()
</script>

<style scoped>
.inline-diagnostic {
  margin-top: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(244, 63, 94, 0.4);
  background: rgba(254, 226, 226, 0.6);
  border-radius: 6px;
  color: #7f1d1d;
  font-size: 0.875rem;
}
.inline-diagnostic-reason {
  margin: 0 0 0.5rem 0;
}
.inline-diagnostic-details summary {
  cursor: pointer;
  font-size: 0.8125rem;
}
.inline-diagnostic-details pre {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 0.75rem;
}
.bc-link {
  background: none;
  border: 0;
  padding: 0;
  margin-top: 0.5rem;
  color: #b91c1c;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.8125rem;
}
</style>
