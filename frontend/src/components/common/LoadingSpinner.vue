<script setup lang="ts">
defineProps<{
  label?: string
}>()
</script>

<template>
  <div class="loading-spinner" role="status" data-testid="loading-spinner">
    <span class="spinner" aria-hidden="true" />
    <span class="label">{{ label ?? 'Loading…' }}</span>
  </div>
</template>

<style scoped>
.loading-spinner {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-text-muted, #6b7280);
  font-size: 0.9rem;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border, #ddd);
  border-top-color: var(--color-accent, #3b82f6);
  border-radius: 50%;
  animation: lsspin 0.8s linear infinite;
}
.label { font-size: inherit; }
@keyframes lsspin {
  to { transform: rotate(360deg); }
}
</style>
