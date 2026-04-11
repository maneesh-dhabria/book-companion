<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const error = ref<Error | null>(null)
const isNetworkError = ref(false)

onErrorCaptured((err) => {
  error.value = err
  isNetworkError.value =
    err.message?.includes('fetch') ||
    err.message?.includes('network') ||
    err.message?.includes('Failed to fetch') ||
    err.name === 'TypeError'
  console.error('[ErrorBoundary]', err)
  return false // prevent propagation
})

function retry() {
  error.value = null
  isNetworkError.value = false
}
</script>

<template>
  <div v-if="error" class="error-boundary">
    <div class="error-content">
      <div class="error-icon">{{ isNetworkError ? '🔌' : '⚠' }}</div>
      <h3 class="error-title">
        {{ isNetworkError ? 'Connection lost' : 'Something went wrong' }}
      </h3>
      <p class="error-description">
        {{ isNetworkError
          ? 'Unable to connect to the server. Please check your connection.'
          : 'An unexpected error occurred. Please try again.'
        }}
      </p>
      <button class="error-retry-btn" @click="retry">
        Try again
      </button>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 2rem;
}

.error-content {
  text-align: center;
  max-width: 400px;
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.error-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.error-description {
  font-size: 0.875rem;
  color: var(--color-text-muted, #888);
  margin-bottom: 1.5rem;
}

.error-retry-btn {
  padding: 0.5rem 1.5rem;
  background: var(--color-accent, #2563eb);
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.error-retry-btn:hover {
  opacity: 0.9;
}
</style>
