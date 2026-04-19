<script setup lang="ts">
import SummarizationProgress from '@/components/book/SummarizationProgress.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import FloatingToolbar from '@/components/reader/FloatingToolbar.vue'
import ReaderHeader from '@/components/reader/ReaderHeader.vue'
import ReadingArea from '@/components/reader/ReadingArea.vue'
import SummaryEmptyState from '@/components/reader/SummaryEmptyState.vue'
import ReaderSettingsPopover from '@/components/settings/ReaderSettingsPopover.vue'
import AIChatTab from '@/components/sidebar/AIChatTab.vue'
import AnnotationsTab from '@/components/sidebar/AnnotationsTab.vue'
import ContextSidebar from '@/components/sidebar/ContextSidebar.vue'
import { useReadingState } from '@/composables/useReadingState'
import { useTextSelection } from '@/composables/useTextSelection'
import { useAnnotationsStore } from '@/stores/annotations'
import { useReaderStore } from '@/stores/reader'
import { useReaderSettingsStore } from '@/stores/readerSettings'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'

const route = useRoute()
const reader = useReaderStore()
const settings = useReaderSettingsStore()
const annotations = useAnnotationsStore()
const job = useSummarizationJobStore()

const readingState = useReadingState(
  () => reader.book?.id,
  () => reader.currentSection?.id,
)

const readingAreaRef = ref<HTMLElement | null>(null)
const sidebarOpen = ref(false)
const { selection, isSelecting, clear: clearSelection } = useTextSelection(readingAreaRef)

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

function handleHighlight() {
  if (!reader.currentSection || !selection.text) return
  annotations.addAnnotation({
    content_type: 'section_content',
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
  const note = prompt('Add a note:')
  if (note === null) return
  annotations.addAnnotation({
    content_type: 'section_content',
    content_id: reader.currentSection.id,
    type: 'note',
    selected_text: selection.text,
    text_start: selection.startOffset,
    text_end: selection.endOffset,
    note,
  })
  clearSelection()
  sidebarOpen.value = true
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
      <SummarizationProgress
        v-if="reader.book.summary_progress"
        :book-id="reader.book.id"
        :summarized="reader.book.summary_progress.summarized"
        :total="reader.book.summary_progress.total"
      />
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
                @click="settings.popoverOpen = !settings.popoverOpen"
                title="Reader settings"
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
          <template v-if="reader.currentSection">
            <template v-if="reader.contentMode === 'summary'">
              <ReadingArea
                v-if="reader.currentSection.default_summary?.summary_md"
                :content="reader.currentSection.default_summary.summary_md"
                :has-prev="reader.hasPrev"
                :has-next="reader.hasNext"
                @navigate="reader.navigateSection($event)"
              />
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
              @navigate="reader.navigateSection($event)"
            />
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
        :visible="isSelecting"
        :rect="selection.rect"
        :selected-text="selection.text"
        @highlight="handleHighlight"
        @note="handleNote"
        @ask-ai="handleAskAi"
        @copy="clearSelection"
      />
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
