<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useReadingStateStore } from '@/stores/readingState'
import { firstChapter, FRONT_MATTER_TYPES } from '@/stores/reader'
import type { Section } from '@/types'

const store = useReadingStateStore()
const router = useRouter()

interface BookShape {
  status: string | null
  sections: Section[]
}
const book = ref<BookShape | null>(null)

async function loadBook(bookId: number) {
  try {
    const r = await fetch(`/api/v1/books/${bookId}`)
    if (!r.ok) return
    const data = await r.json()
    book.value = {
      status: data.status ?? null,
      sections: (data.sections ?? []) as Section[],
    }
  } catch {
    book.value = null
  }
}

onMounted(async () => {
  if (store.isDismissed()) return
  await store.fetchContinueReading()
  if (store.continueReading) await loadBook(store.continueReading.bookId)
})

watch(
  () => store.continueReading?.bookId,
  async (id) => {
    if (id != null) await loadBook(id)
  },
)

const recordedSection = computed<Section | null>(() => {
  if (!store.continueReading?.sectionId || !book.value) return null
  return (
    book.value.sections.find((s) => s.id === store.continueReading!.sectionId) ?? null
  )
})

const needsFallback = computed(() => {
  if (!store.continueReading) return false
  if (store.continueReading.sectionId == null) return true
  const sec = recordedSection.value
  // If we know the section type and it's front-matter, fall back. If we don't
  // know (book not loaded yet, or section missing from the list), trust the
  // recorded id — the server-side filter already prevents front-matter from
  // being persisted in the common path.
  if (sec && FRONT_MATTER_TYPES.has(sec.section_type)) return true
  return false
})

const target = computed<Section | null>(() => {
  if (!store.continueReading) return null
  if (!needsFallback.value && recordedSection.value) return recordedSection.value
  if (book.value) return firstChapter(book.value.sections, book.value.status)
  return null
})

const visible = computed(() => {
  if (!store.continueReading || store.isDismissed()) return false
  // When fallback is needed but the book hasn't loaded yet, hide the banner
  // until we can resolve a real chapter — better than flashing "Continue" and
  // landing on the cover page.
  if (needsFallback.value && !book.value) return false
  if (needsFallback.value && !target.value) return false
  return true
})

const label = computed(() => (needsFallback.value ? 'Start reading' : 'Continue'))

function handleContinue() {
  if (!store.continueReading) return
  const t = target.value
  if (t) {
    router.push(`/books/${store.continueReading.bookId}/sections/${t.id}`)
  } else {
    router.push(`/books/${store.continueReading.bookId}`)
  }
}
</script>

<template>
  <div v-if="visible" class="continue-banner" data-testid="continue-banner">
    <div class="banner-content">
      <span class="banner-icon" aria-hidden="true">📖</span>
      <span class="banner-text">
        <template v-if="needsFallback">
          <strong>{{ store.continueReading!.bookTitle }}</strong>
          <template v-if="target">
            , <strong>{{ target.title }}</strong>
          </template>
        </template>
        <template v-else>
          You were reading <strong>{{ store.continueReading!.bookTitle }}</strong>
          <template v-if="store.continueReading!.sectionTitle">
            , <strong>{{ store.continueReading!.sectionTitle }}</strong>
          </template>
        </template>
      </span>
      <button class="banner-btn" data-testid="continue-banner-btn" @click="handleContinue">
        {{ label }}
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
