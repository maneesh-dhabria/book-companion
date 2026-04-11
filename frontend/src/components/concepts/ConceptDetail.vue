<script setup lang="ts">
import { useConceptsStore } from '@/stores/concepts'
import { ref, watch } from 'vue'

const store = useConceptsStore()
const editing = ref(false)
const editDefinition = ref('')

watch(
  () => store.selectedConcept,
  (c) => {
    editing.value = false
    editDefinition.value = c?.definition || ''
  },
)

function startEdit() {
  editDefinition.value = store.selectedConcept?.definition || ''
  editing.value = true
}

async function saveEdit() {
  if (!store.selectedConcept) return
  await store.editDefinition(store.selectedConcept.id, editDefinition.value)
  editing.value = false
}

async function reset() {
  if (!store.selectedConcept) return
  await store.resetToOriginal(store.selectedConcept.id)
}
</script>

<template>
  <div class="concept-detail" v-if="store.selectedConcept">
    <div class="detail-header">
      <h2 class="concept-term">{{ store.selectedConcept.term }}</h2>
      <span class="book-title">{{ store.selectedConcept.book_title }}</span>
      <span v-if="store.selectedConcept.user_edited" class="edited-badge">User Edited</span>
    </div>

    <div class="detail-section">
      <h3>Definition</h3>
      <template v-if="!editing">
        <p class="definition-text">{{ store.selectedConcept.definition }}</p>
        <div class="definition-actions">
          <button class="action-btn" @click="startEdit">Edit</button>
          <button v-if="store.selectedConcept.user_edited" class="action-btn" @click="reset">
            Reset to Original
          </button>
        </div>
      </template>
      <template v-else>
        <textarea v-model="editDefinition" class="definition-editor" rows="4" />
        <div class="definition-actions">
          <button class="action-btn primary" @click="saveEdit">Save</button>
          <button class="action-btn" @click="editing = false">Cancel</button>
        </div>
      </template>
    </div>

    <div v-if="store.selectedConcept.section_appearances.length" class="detail-section">
      <h3>Appears in Sections</h3>
      <ul class="section-list">
        <li v-for="section in store.selectedConcept.section_appearances" :key="section.id">
          <RouterLink :to="`/books/${store.selectedConcept.book_id}/sections/${section.id}`">
            {{ section.title }}
          </RouterLink>
        </li>
      </ul>
    </div>

    <div v-if="store.selectedConcept.related_concepts.length" class="detail-section">
      <h3>Related Concepts</h3>
      <div class="related-chips">
        <button
          v-for="related in store.selectedConcept.related_concepts"
          :key="related.id"
          class="related-chip"
          @click="store.selectConcept(related.id)"
        >
          {{ related.term }}
        </button>
      </div>
    </div>
  </div>
  <div v-else class="no-selection">
    <p>Select a concept from the list to view details.</p>
  </div>
</template>

<style scoped>
.concept-detail { padding: 1.5rem; overflow-y: auto; }
.no-selection { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--color-text-secondary, #888); }
.detail-header { margin-bottom: 1.5rem; }
.concept-term { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.25rem; }
.book-title { font-size: 0.85rem; color: var(--color-text-secondary, #666); }
.edited-badge { display: inline-block; margin-left: 0.5rem; font-size: 0.7rem; color: var(--color-primary, #3b82f6); background: var(--color-primary-light, #eff6ff); padding: 0.125rem 0.375rem; border-radius: 0.25rem; }
.detail-section { margin-bottom: 1.25rem; }
.detail-section h3 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary, #666); margin: 0 0 0.5rem; }
.definition-text { font-size: 0.9rem; line-height: 1.6; }
.definition-editor { width: 100%; padding: 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; font-size: 0.9rem; font-family: inherit; resize: vertical; }
.definition-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
.action-btn { padding: 0.375rem 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; font-size: 0.8rem; }
.action-btn.primary { background: var(--color-primary, #3b82f6); color: #fff; border-color: var(--color-primary, #3b82f6); }
.section-list { list-style: none; padding: 0; }
.section-list li { padding: 0.25rem 0; }
.section-list a { color: var(--color-primary, #3b82f6); text-decoration: none; font-size: 0.85rem; }
.related-chips { display: flex; flex-wrap: wrap; gap: 0.375rem; }
.related-chip { padding: 0.25rem 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 1rem; background: none; cursor: pointer; font-size: 0.8rem; }
.related-chip:hover { background: var(--color-bg-hover, #f3f4f6); }
</style>
