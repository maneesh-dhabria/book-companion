<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useReadingStateStore } from '@/stores/readingState'

const store = useReadingStateStore()
const router = useRouter()

onMounted(async () => {
  if (!store.isDismissed()) {
    await store.fetchContinueReading()
  }
})

function handleContinue() {
  if (!store.continueReading) return
  const { bookId, sectionId } = store.continueReading
  if (sectionId) {
    router.push(`/books/${bookId}/sections/${sectionId}`)
  } else {
    router.push(`/books/${bookId}`)
  }
}
</script>

<template>
  <div
    v-if="store.continueReading && !store.isDismissed()"
    class="continue-banner"
    data-testid="continue-banner"
  >
    <div class="banner-content">
      <span class="banner-text">
        You were reading <strong>{{ store.continueReading.bookTitle }}</strong>
        <template v-if="store.continueReading.sectionTitle">
          , <strong>{{ store.continueReading.sectionTitle }}</strong>
        </template>
      </span>
      <button class="banner-btn" data-testid="continue-banner-btn" @click="handleContinue">
        Continue
      </button>
    </div>
    <button
      class="banner-dismiss"
      data-testid="continue-banner-dismiss"
      aria-label="Dismiss"
      @click="store.dismiss()"
    >
      &times;
    </button>
  </div>
</template>

<style scoped>
.continue-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--color-accent-light, #eff6ff);
  border: 1px solid var(--color-accent, #2563eb);
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.banner-text {
  font-size: 0.875rem;
}

.banner-btn {
  padding: 0.375rem 0.75rem;
  background: var(--color-accent, #2563eb);
  color: white;
  border: none;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.banner-btn:hover {
  opacity: 0.9;
}

.banner-dismiss {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--color-text-muted, #888);
  cursor: pointer;
  padding: 0 0.25rem;
  line-height: 1;
  margin-left: 0.5rem;
}
</style>
