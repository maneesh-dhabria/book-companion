<template>
  <main class="book-overview">
    <div v-if="loading" class="loading">Loading book…</div>
    <template v-else-if="book">
      <header class="book-header">
        <CoverFallback
          v-if="!book.cover_url"
          :title="book.title"
          :width="140"
          :height="200"
        />
        <img
          v-else
          :src="book.cover_url"
          :alt="`Cover for ${book.title}`"
          class="cover"
        />
        <div class="meta">
          <h1>{{ book.title }}</h1>
          <div class="authors">
            <span v-for="a in book.authors || []" :key="a.id">{{ a.name }}</span>
          </div>
          <div class="book-tags">
            <TagChip
              v-for="t in bookTags"
              :key="t.name"
              :label="t.name"
              :color="t.color"
              removable
              @remove="removeTag(t.name)"
            />
            <TagChipInput
              :model-value="[]"
              :suggest="suggest"
              @update:model-value="onAddTags"
            />
          </div>
          <SuggestedTagsBar
            v-if="suggestedTags.length"
            :suggestions="suggestedTags"
            @accept="acceptSuggestion"
            @reject="rejectSuggestion"
          />
          <SummarizationProgress
            v-if="book.summary_progress && book.summary_progress.summarizable > 0"
            :book-id="book.id"
            :summarized="book.summary_progress.summarized"
            :total="book.summary_progress.summarizable"
            :failed-and-pending="book.summary_progress.failed_and_pending"
          />
          <div class="action-row">
            <router-link
              v-if="firstSection"
              class="btn-primary"
              data-action="read"
              :to="{
                name: 'section-detail',
                params: { id: String(book.id), sectionId: String(firstSection.id) },
              }"
            >
              Read
            </router-link>
            <router-link
              class="btn-secondary"
              data-action="read-summary"
              :class="{ 'is-disabled': !hasBookSummary }"
              :aria-disabled="!hasBookSummary || undefined"
              :title="hasBookSummary ? '' : 'No book summary yet — summarize sections first.'"
              :to="
                hasBookSummary
                  ? { name: 'book-summary', params: { id: String(book.id) } }
                  : { name: 'book-overview', params: { id: String(book.id) } }
              "
              @click="(e: MouseEvent) => !hasBookSummary && e.preventDefault()"
            >
              Read Summary
            </router-link>
            <ExportSplitButton
              data-action="export"
              data-testid="export-summary-btn"
              :disabled="exportDisabled"
              :disabled-reason="disabledTooltip()"
              :loading="exporting"
              @download="onExportClick"
              @copy="onCopyClick"
            />
            <a
              class="customize-link"
              data-testid="customize-export-link"
              :class="{ disabled: customizeDisabled }"
              :aria-disabled="customizeDisabled"
              @click.prevent="customizeDisabled ? null : (showModal = true)"
            >
              Customize…
            </a>
            <OverflowMenu
              data-action="overflow"
              :edit-route="{ name: 'book-edit-structure', params: { id: String(book.id) } }"
              @open-reader-settings="settings.popoverOpen = true"
            />
            <ReaderSettingsPopover />
          </div>
          <ExportCustomizeModal
            v-if="showModal && book"
            :book-id="bookId"
            :book="book"
            @close="showModal = false"
          />
        </div>
      </header>

      <section v-if="defaultSummary" class="summary">
        <h2>Summary</h2>
        <MarkdownRenderer :content="defaultSummary" />
      </section>

      <section class="sections-toc">
        <h2>Sections</h2>
        <SectionListTable
          :sections="(book.sections || []) as SectionRow[]"
          :book-id="book.id"
          :compact="false"
        />
      </section>
    </template>
    <div v-else class="error">Book not found.</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import CoverFallback from '@/components/common/CoverFallback.vue'
import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'
import TagChip from '@/components/common/TagChip.vue'
import TagChipInput from '@/components/common/TagChipInput.vue'
import SuggestedTagsBar from '@/components/book/SuggestedTagsBar.vue'
import SummarizationProgress from '@/components/book/SummarizationProgress.vue'
import ExportCustomizeModal from '@/components/book/ExportCustomizeModal.vue'
import SectionListTable from '@/components/book/SectionListTable.vue'
import ExportSplitButton from '@/components/book/ExportSplitButton.vue'
import OverflowMenu from '@/components/book/OverflowMenu.vue'
import ReaderSettingsPopover from '@/components/settings/ReaderSettingsPopover.vue'
import { exportBookSummary } from '@/api/export'
import { useUiStore } from '@/stores/ui'
import { useReaderSettingsStore } from '@/stores/readerSettings'

interface SectionRow {
  id: number
  title: string
  order_index: number
  section_type: string
  content_char_count?: number | null
  has_summary: boolean
  default_summary?: { summary_char_count: number } | null
  last_failure_type?: string | null
}

interface BookTag {
  id: number
  name: string
  color: string | null
}

const route = useRoute()
const loading = ref(true)
const book = ref<any>(null)
const bookTags = ref<BookTag[]>([])
const defaultSummary = ref<string | null>(null)

const bookId = computed(() => Number(route.params.id))
const firstSection = computed(() => (book.value?.sections || [])[0] ?? null)
const suggestedTags = computed<string[]>(() => book.value?.suggested_tags || [])

const showModal = ref(false)
const exporting = ref(false)
const ui = useUiStore()
const settings = useReaderSettingsStore()

const hasBookSummary = computed(
  () => !!book.value?.default_summary || !!book.value?.default_summary_id,
)

const isProcessingStatus = computed(
  () =>
    !!book.value &&
    (book.value.status === 'UPLOADING' || book.value.status === 'PARSING'),
)
const hasNoSummaries = computed(() => {
  if (!book.value) return true
  // Live API exposes default_summary_id; the typed Book interface uses
  // default_summary?: SummaryBrief. Defensive check for both.
  const hasBookSummary =
    !!book.value.default_summary || !!book.value.default_summary_id
  const hasAnySectionSummary = (book.value.sections || []).some(
    (s: {
      has_summary?: boolean
      default_summary_id?: number | null
      default_summary?: unknown
    }) => s.has_summary || s.default_summary_id || s.default_summary,
  )
  return !hasBookSummary && !hasAnySectionSummary
})
const exportDisabled = computed(
  () => isProcessingStatus.value || hasNoSummaries.value || exporting.value,
)
const customizeDisabled = computed(() => isProcessingStatus.value)

function disabledTooltip(): string {
  if (isProcessingStatus.value) return 'Book is still being processed.'
  if (hasNoSummaries.value) return 'Generate a summary first.'
  return ''
}

async function onExportClick() {
  if (exportDisabled.value) return
  exporting.value = true
  try {
    const r = await exportBookSummary(bookId.value)
    const url = URL.createObjectURL(r.blob)
    const a = document.createElement('a')
    a.href = url
    a.download = r.filename
    a.click()
    URL.revokeObjectURL(url)
    ui.showToast(
      r.isEmpty ? 'Summary exported (empty)' : `Summary exported as ${r.filename}`,
      'success',
    )
  } catch {
    ui.showToast('Export failed -- check your connection.', 'error')
  } finally {
    exporting.value = false
  }
}

async function onCopyClick() {
  if (exportDisabled.value) return
  exporting.value = true
  const url = `/api/v1/export/book/${bookId.value}?format=markdown`
  const winClipboardItem = (window as unknown as { ClipboardItem?: typeof ClipboardItem })
    .ClipboardItem
  const navClipboardWrite = (
    navigator.clipboard as unknown as { write?: (items: ClipboardItem[]) => Promise<void> }
  ).write
  try {
    if (navClipboardWrite && winClipboardItem) {
      let isEmpty = false
      const fetchPromise = fetch(url).then((r) => {
        if (!r.ok) throw new Error('fetch failed')
        isEmpty = r.headers.get('x-empty-export') === 'true'
        return r.blob()
      })
      try {
        await navigator.clipboard.write([
          new winClipboardItem({ 'text/plain': fetchPromise }),
        ])
        ui.showToast(
          isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
          'success',
        )
      } catch (err) {
        if (err instanceof Error && err.message === 'fetch failed') {
          ui.showToast('Export failed -- check your connection.', 'error')
        } else {
          ui.showToast("Couldn't copy -- try Export instead.", 'error')
        }
      }
    } else {
      const resp = await fetch(url)
      if (!resp.ok) {
        ui.showToast('Export failed -- check your connection.', 'error')
        return
      }
      const isEmpty = resp.headers.get('x-empty-export') === 'true'
      const text = await resp.text()
      try {
        await navigator.clipboard.writeText(text)
        ui.showToast(
          isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
          'success',
        )
      } catch {
        ui.showToast("Couldn't copy -- try Export instead.", 'error')
      }
    }
  } finally {
    exporting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const [bookResp, tagsResp] = await Promise.all([
      fetch(`/api/v1/books/${bookId.value}`),
      fetch(`/api/v1/books/${bookId.value}/tags`),
    ])
    if (bookResp.ok) book.value = await bookResp.json()
    if (tagsResp.ok) bookTags.value = (await tagsResp.json()).tags
    // Pull default book summary — optional.
    try {
      const r = await fetch(`/api/v1/books/${bookId.value}/summary`)
      if (r.ok) {
        const payload = await r.json()
        defaultSummary.value = payload?.summary_md || null
      }
    } catch {
      defaultSummary.value = null
    }
  } finally {
    loading.value = false
  }
}

async function suggest(q: string) {
  const resp = await fetch(`/api/v1/tags/suggest?q=${encodeURIComponent(q)}`)
  if (!resp.ok) return []
  const body = await resp.json()
  return (body.suggestions || []).map((s: { name: string }) => s.name)
}

async function onAddTags(tags: string[]) {
  for (const name of tags) {
    const resp = await fetch(`/api/v1/books/${bookId.value}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (resp.ok) {
      const body = await resp.json()
      if (!bookTags.value.some((t) => t.id === body.id))
        bookTags.value.push(body)
    }
  }
}

async function removeTag(name: string) {
  const tag = bookTags.value.find((t) => t.name === name)
  if (!tag) return
  await fetch(`/api/v1/books/${bookId.value}/tags/${tag.id}`, { method: 'DELETE' })
  bookTags.value = bookTags.value.filter((t) => t.id !== tag.id)
}

async function acceptSuggestion(name: string) {
  await onAddTags([name])
  await rejectSuggestion(name)
}

async function rejectSuggestion(name: string) {
  const resp = await fetch(`/api/v1/books/${bookId.value}/suggested-tags`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reject: [name] }),
  })
  if (resp.ok) {
    const body = await resp.json()
    if (book.value) book.value.suggested_tags = body.suggested_tags
  }
}

onMounted(load)
</script>

<style scoped>
.book-overview {
  max-width: 48rem;
  margin: 0 auto;
  padding: 2rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.book-header {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
}
.cover {
  width: 140px;
  height: 200px;
  object-fit: cover;
  border-radius: 0.25rem;
}
.meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
h1 {
  margin: 0;
  font-size: 1.6rem;
}
.authors span {
  color: #475569;
  font-size: 0.9rem;
}
.authors span + span::before {
  content: ', ';
}
.book-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.progress {
  font-size: 0.875rem;
  color: #475569;
}
.actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}
.actions .cta {
  display: inline-block;
  padding: 0.45rem 1rem;
  border-radius: 0.25rem;
  background: #4f46e5;
  color: white;
  text-decoration: none;
}
.sections-toc ol {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.sections-toc li {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.section-type {
  font-size: 0.75rem;
  color: #94a3b8;
}
.summarized {
  color: #059669;
  font-weight: 700;
}
.loading,
.error {
  padding: 2rem;
  text-align: center;
}
.actions .cta.primary {
  background: var(--color-bg-muted, #f3f4f6);
  color: var(--color-text-primary, #111);
  border: 1px solid var(--color-border, #d1d5db);
  cursor: pointer;
}
.actions .cta.primary:disabled,
.actions .cta.primary[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}
.customize-link {
  font-size: 0.85rem;
  text-decoration: underline;
  color: #4f46e5;
  cursor: pointer;
}
.customize-link.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
