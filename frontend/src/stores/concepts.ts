import { deleteConcept, getConcept, listConcepts, resetConcept, updateConcept } from '@/api/concepts'
import type { Concept, ConceptDetail, PaginatedResponse } from '@/types'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useConceptsStore = defineStore('concepts', () => {
  const concepts = ref<Concept[]>([])
  const total = ref(0)
  const selectedConcept = ref<ConceptDetail | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)

  async function loadConcepts(params?: {
    book_id?: number
    user_edited?: boolean
    sort?: string
    page?: number
  }) {
    loading.value = true
    try {
      const resp: PaginatedResponse<Concept> = await listConcepts(params)
      concepts.value = resp.items
      total.value = resp.total
    } finally {
      loading.value = false
    }
  }

  async function selectConcept(id: number) {
    detailLoading.value = true
    try {
      selectedConcept.value = await getConcept(id)
    } finally {
      detailLoading.value = false
    }
  }

  async function editDefinition(id: number, definition: string) {
    const updated = await updateConcept(id, { definition })
    const idx = concepts.value.findIndex((c) => c.id === id)
    if (idx >= 0) concepts.value[idx] = updated
    if (selectedConcept.value?.id === id) {
      selectedConcept.value = { ...selectedConcept.value, ...updated }
    }
  }

  async function resetToOriginal(id: number) {
    const updated = await resetConcept(id)
    const idx = concepts.value.findIndex((c) => c.id === id)
    if (idx >= 0) concepts.value[idx] = updated
    if (selectedConcept.value?.id === id) {
      selectedConcept.value = { ...selectedConcept.value, ...updated }
    }
  }

  async function removeConcept(id: number) {
    await deleteConcept(id)
    concepts.value = concepts.value.filter((c) => c.id !== id)
    total.value -= 1
    if (selectedConcept.value?.id === id) {
      selectedConcept.value = null
    }
  }

  return {
    concepts,
    total,
    selectedConcept,
    loading,
    detailLoading,
    loadConcepts,
    selectConcept,
    editDefinition,
    resetToOriginal,
    removeConcept,
  }
})
