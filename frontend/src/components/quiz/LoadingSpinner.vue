<template>
  <div data-test="loading-spinner" class="loading-spinner" role="status" aria-live="polite">
    <span class="spinner" aria-hidden="true"></span>
    <span class="copy">{{ copy }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ copy: string }>()
</script>

<style scoped>
.loading-spinner {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--color-text-muted, #555);
  font-size: 0.95rem;
}
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #c7d2fe;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
