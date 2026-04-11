<script setup lang="ts">
import AnnotationCard from './AnnotationCard.vue'
import { useAnnotationsStore } from '@/stores/annotations'
import { onMounted, watch } from 'vue'

const props = defineProps<{
  bookId: number
  sectionId?: number
}>()

const store = useAnnotationsStore()

onMounted(() => loadAnnotations())
watch(() => props.sectionId, () => loadAnnotations())

function loadAnnotations() {
  store.loadAnnotations({
    content_type: 'section_content',
    content_id: props.sectionId,
    book_id: props.sectionId ? undefined : props.bookId,
  })
}
</script>

<template>
  <div class="annotations-tab">
    <div v-if="store.loading" class="loading">Loading annotations...</div>
    <div v-else-if="store.annotations.length === 0" class="empty">
      <p>No annotations yet.</p>
      <p class="hint">Select text to create highlights and notes.</p>
    </div>
    <div v-else class="annotation-list">
      <AnnotationCard
        v-for="annotation in store.annotations"
        :key="annotation.id"
        :annotation="annotation"
        @delete="store.removeAnnotation(annotation.id)"
      />
    </div>
  </div>
</template>

<style scoped>
.annotations-tab { padding: 0.75rem; }
.loading { text-align: center; padding: 2rem; color: var(--color-text-secondary, #888); }
.empty { text-align: center; padding: 2rem; color: var(--color-text-secondary, #888); }
.hint { font-size: 0.8rem; margin-top: 0.5rem; }
.annotation-list { display: flex; flex-direction: column; gap: 0.5rem; }
</style>
