import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
} from '@/api/annotations'
import type { Annotation, PaginatedResponse } from '@/types'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAnnotationsStore = defineStore('annotations', () => {
  const annotations = ref<Annotation[]>([])
  const total = ref(0)
  const loading = ref(false)
  const currentFilter = ref<{
    content_type?: string
    content_id?: number
    book_id?: number
    type?: string
  }>({})

  async function loadAnnotations(filter?: typeof currentFilter.value) {
    loading.value = true
    if (filter) currentFilter.value = filter
    try {
      const resp: PaginatedResponse<Annotation> = await listAnnotations(currentFilter.value)
      annotations.value = resp.items
      total.value = resp.total
    } finally {
      loading.value = false
    }
  }

  async function addAnnotation(data: {
    content_type: string
    content_id: number
    type: string
    selected_text?: string | null
    text_start?: number | null
    text_end?: number | null
    note?: string | null
  }) {
    const annotation = await createAnnotation(data)
    annotations.value.unshift(annotation)
    total.value += 1
    return annotation
  }

  async function editAnnotation(id: number, data: { note?: string | null; type?: string }) {
    const updated = await updateAnnotation(id, data)
    const idx = annotations.value.findIndex((a) => a.id === id)
    if (idx >= 0) annotations.value[idx] = updated
    return updated
  }

  async function removeAnnotation(id: number) {
    await deleteAnnotation(id)
    annotations.value = annotations.value.filter((a) => a.id !== id)
    total.value -= 1
  }

  return {
    annotations,
    total,
    loading,
    currentFilter,
    loadAnnotations,
    addAnnotation,
    editAnnotation,
    removeAnnotation,
  }
})
