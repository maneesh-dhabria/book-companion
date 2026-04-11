<script setup lang="ts">
import { uploadBook } from '@/api/books'
import type { Book } from '@/types'
import { ref } from 'vue'

const props = defineProps<{
  file: File
}>()

const emit = defineEmits<{
  complete: [data: { id: number; title: string; sections: unknown[] }]
  back: []
}>()

const uploading = ref(false)
const error = ref('')

async function handleUpload() {
  uploading.value = true
  error.value = ''
  try {
    const book: Book = await uploadBook(props.file)
    emit('complete', {
      id: book.id,
      title: book.title,
      sections: book.sections,
    })
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="metadata-form">
    <h2>Upload Book</h2>
    <div class="file-info">
      <span class="file-name">{{ file.name }}</span>
      <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(1) }} MB</span>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="form-actions">
      <button class="secondary-btn" @click="$emit('back')">Back</button>
      <button class="primary-btn" @click="handleUpload" :disabled="uploading">
        {{ uploading ? 'Uploading...' : 'Upload & Parse' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.metadata-form { max-width: 500px; margin: 0 auto; }
h2 { font-size: 1.25rem; margin-bottom: 1rem; }
.file-info { display: flex; justify-content: space-between; padding: 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.5rem; margin-bottom: 1rem; }
.file-name { font-weight: 500; }
.file-size { color: var(--color-text-secondary, #888); }
.error { color: var(--color-danger, #ef4444); margin-bottom: 1rem; padding: 0.5rem; background: #fef2f2; border-radius: 0.375rem; }
.form-actions { display: flex; justify-content: space-between; gap: 0.5rem; }
.primary-btn { padding: 0.5rem 1.25rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.secondary-btn { padding: 0.5rem 1.25rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; }
</style>
