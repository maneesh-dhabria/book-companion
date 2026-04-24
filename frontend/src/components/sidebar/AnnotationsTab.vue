<script setup lang="ts">
import AnnotationCard from './AnnotationCard.vue'
import { useAnnotationsStore } from '@/stores/annotations'
import { useReaderSettingsStore } from '@/stores/readerSettings'
import { useReaderStore } from '@/stores/reader'
import { computed, onMounted, watch } from 'vue'

const props = defineProps<{
  bookId: number
  sectionId?: number
}>()

const store = useAnnotationsStore()
const settings = useReaderSettingsStore()
const reader = useReaderStore()

onMounted(() => loadAnnotations())
watch(() => props.sectionId, () => loadAnnotations())
watch(() => settings.annotationsScope, () => loadAnnotations())

function loadAnnotations() {
  if (settings.annotationsScope === 'all') {
    // Book-wide load — all annotations across sections.
    store.loadAnnotations({ content_type: 'section_content', book_id: props.bookId })
    return
  }
  store.loadAnnotations({
    content_type: 'section_content',
    content_id: props.sectionId,
    book_id: props.sectionId ? undefined : props.bookId,
  })
}

// FR-C4.2 — split the rendered list into "current section" + "other chapters"
// when we're scoped to the current section but the store has book-wide state
// (happens after toggling scope). The "Show N from other chapters" toggle
// lives on this computed-split view.
const scopedCurrent = computed(() => {
  if (settings.annotationsScope === 'all' || !props.sectionId) {
    return store.annotations
  }
  return store.annotations.filter((a) => a.content_id === props.sectionId)
})

const otherSectionCount = computed(() => {
  if (settings.annotationsScope === 'all' || !props.sectionId) return 0
  return store.annotations.filter((a) => a.content_id !== props.sectionId).length
})

function scrollToSource(annotationId: number) {
  // FR-C4.3 — find the <mark id="ann-{N}"> anchor inside the reading area
  // and scroll it into view with a brief pulse highlight. The highlight
  // injector guarantees the first split of any multi-block annotation
  // carries id="ann-{N}".
  const el = document.getElementById(`ann-${annotationId}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.classList.add('ann-pulse')
    setTimeout(() => el.classList.remove('ann-pulse'), 1500)
    return
  }
  // Cross-section case — the source annotation lives in another section.
  // Push the router (FR-D2) so the URL reflects the jump, then after the
  // navigation resolves scroll the mark into view with a pulse.
  const target = store.annotations.find((a) => a.id === annotationId)
  if (!target || !reader.book) return
  const section = reader.sections.find((s) => s.id === target.content_id)
  if (!section) return
  const bookId = reader.book.id
  ;(async () => {
    try {
      const router = (await import('@/router')).default
      await router.push({
        name: 'section-detail',
        params: { id: String(bookId), sectionId: String(section.id) },
      })
    } catch {
      reader.loadSection(bookId, section.id)
    }
    setTimeout(() => {
      const el2 = document.getElementById(`ann-${annotationId}`)
      if (el2) {
        el2.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el2.classList.add('ann-pulse')
        setTimeout(() => el2.classList.remove('ann-pulse'), 1500)
      }
    }, 80)
  })()
}

function showAllToggle() {
  settings.annotationsScope = 'all'
}
</script>

<template>
  <div class="annotations-tab">
    <div class="scope-bar">
      <label class="scope-cell">
        <span>Scope</span>
        <select v-model="settings.annotationsScope">
          <option value="current">Current section</option>
          <option value="all">All sections</option>
        </select>
      </label>
      <button
        v-if="settings.annotationsScope === 'current' && otherSectionCount > 0"
        type="button"
        class="show-more"
        @click="showAllToggle"
      >
        Show {{ otherSectionCount }} from other chapters
      </button>
    </div>
    <div v-if="store.loading" class="loading">Loading annotations…</div>
    <div v-else-if="scopedCurrent.length === 0" class="empty">
      <p>No annotations yet.</p>
      <p class="hint">Select text to create highlights and notes.</p>
    </div>
    <div v-else class="annotation-list">
      <AnnotationCard
        v-for="annotation in scopedCurrent"
        :key="annotation.id"
        :annotation="annotation"
        @delete="store.removeAnnotation(annotation.id)"
        @scroll-to-source="scrollToSource(annotation.id)"
      />
    </div>
  </div>
</template>

<style scoped>
.annotations-tab {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.scope-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-secondary, #888);
}
.scope-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.scope-cell select {
  font-size: 0.75rem;
  padding: 0.15rem 0.3rem;
}
.show-more {
  font-size: 0.75rem;
  background: transparent;
  border: 0;
  color: #4f46e5;
  cursor: pointer;
  text-decoration: underline;
}
.loading {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-secondary, #888);
}
.empty {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-secondary, #888);
}
.hint {
  font-size: 0.8rem;
  margin-top: 0.5rem;
}
.annotation-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

:global(.ann-pulse) {
  animation: ann-pulse-anim 1.4s ease-out;
}

@keyframes ann-pulse-anim {
  0% {
    background: rgba(234, 179, 8, 0.6);
  }
  100% {
    background: transparent;
  }
}
</style>
