<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useReaderStore } from '@/stores/reader'
import ReaderHeader from '@/components/reader/ReaderHeader.vue'
import ReadingArea from '@/components/reader/ReadingArea.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const reader = useReaderStore()

async function loadFromRoute() {
  const bookId = Number(route.params.id)
  if (!reader.book || reader.book.id !== bookId) {
    await reader.loadBook(bookId)
  }

  const sectionId = route.params.sectionId
    ? Number(route.params.sectionId)
    : reader.sections[0]?.id

  if (sectionId) {
    await reader.loadSection(bookId, sectionId)
  }
}

onMounted(loadFromRoute)
watch(() => route.params, loadFromRoute)

const displayContent = () => {
  if (!reader.currentSection) return ''
  if (reader.contentMode === 'summary' && reader.currentSection.default_summary) {
    return reader.currentSection.default_summary.summary_char_count > 0
      ? '(Summary content loaded via API)'
      : reader.currentSection.content_md || ''
  }
  return reader.currentSection.content_md || ''
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
      />

      <template v-if="reader.currentSection">
        <ReadingArea
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
    </template>
  </div>
</template>

<style scoped>
.reader-page {
  min-height: 100%;
}
</style>
