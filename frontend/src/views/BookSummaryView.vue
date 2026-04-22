<script setup lang="ts">
import { startBookSummary } from '@/api/bookSummary'
import { getBook } from '@/api/books'
import { connectSSE } from '@/api/processing'
import PresetPickerModal from '@/components/common/PresetPickerModal.vue'
import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'
import type { Book } from '@/types'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const book = ref<Book | null>(null)
const loadError = ref<string | null>(null)
const modalOpen = ref(false)
const generating = ref(false)
const generateError = ref<string | null>(null)
const activeJobId = ref<number | null>(null)
let activeSource: EventSource | null = null

const bookId = computed(() => Number(route.params.id))

const progress = computed(() => book.value?.summary_progress ?? null)
const hasBookSummary = computed(
  () => book.value != null && book.value.default_summary != null,
)
const noSections = computed(
  () => (progress.value?.summarized ?? 0) === 0,
)
const lastUsedPreset = computed<string | null>(() => {
  const maybe = book.value as (Book & { last_used_preset?: string | null }) | null
  return maybe?.last_used_preset ?? null
})

async function fetchBook() {
  try {
    book.value = await getBook(bookId.value)
    loadError.value = null
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Could not load book'
  }
}

onMounted(fetchBook)
watch(bookId, fetchBook)

function closeSource() {
  if (activeSource) {
    activeSource.close()
    activeSource = null
  }
}

onUnmounted(closeSource)

function openModal() {
  if (noSections.value || generating.value) return
  modalOpen.value = true
}

async function onSubmit(presetId: string) {
  modalOpen.value = false
  generating.value = true
  generateError.value = null
  try {
    const { job_id } = await startBookSummary(bookId.value, {
      preset_name: presetId,
    })
    activeJobId.value = job_id
    activeSource = connectSSE(job_id, {
      onProcessingCompleted: async (data) => {
        generating.value = false
        if (data.book_summary_id) {
          await fetchBook()
        }
        closeSource()
      },
      onProcessingFailed: (data) => {
        generating.value = false
        generateError.value = data.error || 'Book summary generation failed'
        closeSource()
      },
      onError: () => {
        // Server closed the stream or transient error — keep the UI in
        // "generating" for a bit; the next fetchBook on completion-like
        // signal will reconcile.
      },
    })
  } catch (err) {
    generating.value = false
    generateError.value = err instanceof Error ? err.message : 'Network error'
  }
}

function onCancel() {
  modalOpen.value = false
}
</script>

<template>
  <div class="book-summary-view">
    <div v-if="loadError" class="error">Could not load book: {{ loadError }}</div>
    <template v-else-if="book">
      <header class="page-header">
        <h1>{{ book.title }}</h1>
        <p v-if="progress" class="progress">
          {{ progress.summarized }} of {{ progress.total }} sections summarized
        </p>
      </header>

      <section v-if="hasBookSummary" class="summary">
        <MarkdownRenderer
          :content="book.default_summary?.summary_md ?? ''"
        />
      </section>
      <section v-else class="summary-empty">
        <p>
          A book-level summary synthesizes all section summaries into one
          document.
        </p>
      </section>

      <div class="actions">
        <button
          type="button"
          class="primary-btn"
          data-testid="generate-btn"
          :disabled="noSections || generating"
          :title="noSections ? 'Summarize sections first' : undefined"
          @click="openModal"
        >
          <span v-if="generating">Generating…</span>
          <span v-else-if="hasBookSummary">Regenerate book summary</span>
          <span v-else>Generate book summary</span>
        </button>
      </div>

      <p v-if="generateError" class="error" role="alert">{{ generateError }}</p>

      <PresetPickerModal
        v-if="modalOpen"
        :preselect="lastUsedPreset"
        title="Book summary preset"
        submit-label="Generate"
        @submit="onSubmit"
        @cancel="onCancel"
      />
    </template>
  </div>
</template>

<style scoped>
.book-summary-view {
  max-width: 780px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.page-header h1 { margin: 0; font-size: 1.6rem; font-weight: 600; }
.progress { color: var(--color-text-muted, #6b7280); font-size: 0.9rem; margin: 0.25rem 0 0; }
.summary { border-top: 1px solid var(--color-border, #e5e7eb); padding-top: 1rem; }
.summary-empty { color: var(--color-text-muted, #6b7280); font-size: 0.95rem; }
.actions { display: flex; gap: 0.5rem; }
.primary-btn {
  padding: 0.6rem 1.25rem;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.95rem;
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  color: var(--color-danger, #b91c1c);
  background: var(--color-danger-light, #fef2f2);
  border: 1px solid var(--color-danger, #b91c1c);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  margin: 0;
  font-size: 0.9rem;
}
</style>
