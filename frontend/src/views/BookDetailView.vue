<script setup lang="ts">
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import FloatingToolbar from '@/components/reader/FloatingToolbar.vue'
import ReaderHeader from '@/components/reader/ReaderHeader.vue'
import ReadingArea from '@/components/reader/ReadingArea.vue'
import ReadingAreaFooterNav from '@/components/reader/ReadingAreaFooterNav.vue'
import SummaryEmptyState from '@/components/reader/SummaryEmptyState.vue'
import ReaderSettingsPopover from '@/components/settings/ReaderSettingsPopover.vue'
import AIChatTab from '@/components/sidebar/AIChatTab.vue'
import AnnotationsTab from '@/components/sidebar/AnnotationsTab.vue'
import ContextSidebar from '@/components/sidebar/ContextSidebar.vue'
import NoteCompositionPanel from '@/components/sidebar/NoteCompositionPanel.vue'
import { useReadingState } from '@/composables/useReadingState'
import { useTextSelection } from '@/composables/useTextSelection'
import { useAnnotationsStore } from '@/stores/annotations'
import { annotationContentTypeFor } from '@/utils/annotationContentType'
import { useReaderStore } from '@/stores/reader'
import { useReaderSettingsStore } from '@/stores/readerSettings'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'

const route = useRoute()
const reader = useReaderStore()
const settings = useReaderSettingsStore()
const annotations = useAnnotationsStore()
const job = useSummarizationJobStore()

const readingState = useReadingState(
  () => reader.book?.id,
  () => reader.currentSection?.id,
  () => reader.currentSection?.section_type,
)

const readingAreaRef = ref<HTMLElement | null>(null)
const sidebarOpen = ref(false)
const { selection, isSelecting, clear: clearSelection } = useTextSelection(readingAreaRef)

// Only inject inline highlights for annotations whose content_id matches the
// CURRENT section. Without this guard, scope='all' would let cross-section
// annotations accidentally match text fragments in unrelated sections and
// render misleading marks with the wrong scroll anchor.
const inlineAnnotations = computed(() => {
  const currentId = reader.currentSection?.id
  if (currentId == null) return []
  // Each tab projects only the annotations that target its content_type so
  // Summary-tab highlights don't bleed into the Original tab and vice versa.
  const wantedType = annotationContentTypeFor(
    reader.contentMode === 'summary' ? 'summary' : 'original',
  )
  return annotations.annotations.filter(
    (a) => a.content_id === currentId && a.content_type === wantedType,
  )
})

// T29 — NoteCompositionPanel replaces prompt(). Capture the selection
// before opening the panel so the user can edit without losing anchor.
const notePanelOpen = ref(false)
const pendingSelection = ref<{
  text: string
  startOffset: number | null
  endOffset: number | null
} | null>(null)

async function loadFromRoute() {
  const bookId = Number(route.params.id)
  const routeSectionId = route.params.sectionId
    ? Number(route.params.sectionId)
    : undefined
  const savedSectionId =
    (readingState as { savedSectionId?: { value?: number | null } } | undefined)
      ?.savedSectionId?.value ?? undefined

  if (!reader.book || reader.book.id !== bookId) {
    await reader.loadBook(bookId, {
      routeSectionId,
      savedSectionId: savedSectionId ?? undefined,
    })
  } else if (routeSectionId && routeSectionId !== reader.currentSection?.id) {
    await reader.loadSection(bookId, routeSectionId)
  }
}

async function onSummarizeThisSection() {
  if (!reader.book || !reader.currentSection) return
  await job.startJob(reader.book.id, {
    scope: 'section',
    section_id: reader.currentSection.id,
  })
}

onBeforeRouteLeave(() => {
  job.reset()
})

onMounted(() => {
  loadFromRoute()
  settings.loadPresets()
})
watch(() => route.params, loadFromRoute)

// v1.5 T22 — keep the annotations store in sync with the current section so
// MarkdownRenderer can wrap highlights inline without waiting for the
// sidebar to open. Respects the annotationsScope toggle in readerSettings.
watch(
  [() => reader.currentSection?.id, () => settings.annotationsScope, () => reader.book?.id],
  () => {
    if (!reader.book) return
    if (settings.annotationsScope === 'all') {
      // Load both section_content and section_summary annotations; the
      // tab-level filter below picks the right subset for inline highlighting.
      annotations.loadAnnotations({ book_id: reader.book.id })
    } else if (reader.currentSection) {
      annotations.loadAnnotations({ content_id: reader.currentSection.id })
    }
  },
  { immediate: true },
)

function handleHighlight() {
  if (!reader.currentSection || !selection.text) return
  annotations.addAnnotation({
    content_type: annotationContentTypeFor(
      reader.contentMode === 'summary' ? 'summary' : 'original',
    ),
    content_id: reader.currentSection.id,
    type: 'highlight',
    selected_text: selection.text,
    text_start: selection.startOffset,
    text_end: selection.endOffset,
  })
  clearSelection()
  sidebarOpen.value = true
}

function handleNote() {
  if (!reader.currentSection || !selection.text) return
  pendingSelection.value = {
    text: selection.text,
    startOffset: selection.startOffset,
    endOffset: selection.endOffset,
  }
  notePanelOpen.value = true
  // Keep the selection visible behind the panel; clearing happens on save/close.
}

function onNoteSave(note: string) {
  if (!reader.currentSection || !pendingSelection.value) return
  annotations.addAnnotation({
    content_type: annotationContentTypeFor(
      reader.contentMode === 'summary' ? 'summary' : 'original',
    ),
    content_id: reader.currentSection.id,
    type: 'note',
    selected_text: pendingSelection.value.text,
    text_start: pendingSelection.value.startOffset,
    text_end: pendingSelection.value.endOffset,
    note,
  })
  notePanelOpen.value = false
  pendingSelection.value = null
  clearSelection()
  sidebarOpen.value = true
}

function onNoteClose() {
  notePanelOpen.value = false
  pendingSelection.value = null
  clearSelection()
}

function handleAskAi() {
  sidebarOpen.value = true
  clearSelection()
}
</script>

<template>
  <div class="reader-page">
    <template v-if="reader.loading && !reader.book">
      <div style="padding: 32px">
        <SkeletonLoader type="text" :count="5" />
      </div>
    </template>

    <template v-else-if="!reader.book">
      <EmptyState
        icon="📖"
        title="Book not found"
        description="The book you're looking for doesn't exist."
        action-label="Back to Library"
        action-to="/"
      />
    </template>

    <template v-else>
      <ReaderHeader
        :book-title="reader.book.title"
        :book-id="reader.book.id"
        :sections="reader.sections"
        :current-section-id="reader.currentSection?.id ?? null"
        :content-mode="reader.contentMode"
        :has-summary="reader.hasSummary"
        :has-prev="reader.hasPrev"
        :has-next="reader.hasNext"
        @toggle-content="reader.toggleContent()"
        @navigate="reader.navigateSection($event)"
      >
        <template #actions>
          <div class="reader-actions">
            <button
              class="action-btn"
              :class="{ active: sidebarOpen }"
              @click="sidebarOpen = !sidebarOpen"
              title="Toggle sidebar"
            >
              ☰
            </button>
            <div class="settings-wrapper">
              <button
                class="action-btn"
                aria-label="Reader settings"
                title="Reader settings"
                @click="settings.popoverOpen = !settings.popoverOpen"
              >
                ⚙
              </button>
              <ReaderSettingsPopover />
            </div>
          </div>
        </template>
      </ReaderHeader>

      <div class="reader-body">
        <div class="reader-content" ref="readingAreaRef">
          <div
            v-if="reader.loading && reader.book"
            class="reader-loading"
            data-testid="reader-loading"
          >
            <LoadingSpinner label="Loading section…" />
          </div>
          <template v-else-if="reader.currentSection">
            <template v-if="reader.contentMode === 'summary'">
              <ReadingArea
                v-if="reader.currentSection.default_summary?.summary_md"
                :content="reader.currentSection.default_summary.summary_md"
                :has-prev="reader.hasPrev"
                :has-next="reader.hasNext"
                @navigate="reader.navigateSection($event)"
              >
                <template #footer>
                  <ReadingAreaFooterNav
                    v-if="reader.book"
                    :book-id="reader.book.id"
                    :prev="reader.prevSection ? { id: reader.prevSection.id, title: reader.prevSection.title } : null"
                    :next="reader.nextSection ? { id: reader.nextSection.id, title: reader.nextSection.title } : null"
                    current-tab="summary"
                  />
                </template>
              </ReadingArea>
              <SummaryEmptyState
                v-else
                :section="reader.currentSection"
                :active-job-section-id="job.activeJobSectionId"
                :failed-error="job.getFailedError(reader.currentSection.id) ?? null"
                @summarize="onSummarizeThisSection"
              />
            </template>
            <ReadingArea
              v-else
              :content="reader.currentSection.content_md || ''"
              :has-prev="reader.hasPrev"
              :has-next="reader.hasNext"
              :annotations="inlineAnnotations"
              :highlights-inline="settings.highlightsVisible"
              @navigate="reader.navigateSection($event)"
            >
              <template #footer>
                <ReadingAreaFooterNav
                  v-if="reader.book"
                  :book-id="reader.book.id"
                  :prev="reader.prevSection ? { id: reader.prevSection.id, title: reader.prevSection.title } : null"
                  :next="reader.nextSection ? { id: reader.nextSection.id, title: reader.nextSection.title } : null"
                  current-tab="original"
                />
              </template>
            </ReadingArea>
          </template>

          <template v-else-if="reader.sections.length === 0">
            <EmptyState
              icon="📄"
              title="No sections"
              description="This book has no sections yet."
            />
          </template>
        </div>

        <ContextSidebar :open="sidebarOpen" @close="sidebarOpen = false">
          <template #annotations>
            <AnnotationsTab
              :book-id="reader.book.id"
              :section-id="reader.currentSection?.id"
            />
          </template>
          <template #ai>
            <AIChatTab
              :book-id="reader.book.id"
              :section-id="reader.currentSection?.id"
              :selected-text="selection.text || undefined"
            />
          </template>
        </ContextSidebar>
      </div>

      <FloatingToolbar
        :visible="isSelecting && !notePanelOpen"
        :rect="selection.rect"
        :selected-text="selection.text"
        @highlight="handleHighlight"
        @note="handleNote"
        @ask-ai="handleAskAi"
        @copy="clearSelection"
      />

      <!-- T29 — slide-in note editor; replaces prompt() -->
      <div v-if="notePanelOpen" class="note-panel-host" role="dialog">
        <NoteCompositionPanel
          :visible="notePanelOpen"
          :context="pendingSelection?.text"
          @save="onNoteSave"
          @close="onNoteClose"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.reader-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.reader-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.reader-content {
  flex: 1;
  overflow-y: auto;
}

.note-panel-host {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(420px, 95vw);
  background: white;
  border-left: 1px solid #e5e7eb;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.08);
  z-index: 40;
  display: flex;
  flex-direction: column;
}

.reader-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 64px 24px;
}

.reader-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.action-btn.active {
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
}

.settings-wrapper {
  position: relative;
}
</style>
