<script setup lang="ts">
defineProps<{
  message?: string
}>()
defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="presets-fetch-error" role="alert">
    <p class="error-title">Could not load summarization presets.</p>
    <p v-if="message" class="error-detail">{{ message }}</p>
    <button
      type="button"
      class="retry-btn"
      data-testid="presets-fetch-retry"
      @click="$emit('retry')"
    >
      Retry
    </button>
  </div>
</template>

<style scoped>
.presets-fetch-error {
  border: 1px solid var(--color-danger, #b91c1c);
  background: var(--color-danger-light, #fee2e2);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.error-title { font-weight: 600; margin: 0; }
.error-detail { margin: 0; font-size: 0.85rem; opacity: 0.85; }
.retry-btn {
  align-self: flex-start;
  padding: 0.4rem 0.9rem;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}
</style>
