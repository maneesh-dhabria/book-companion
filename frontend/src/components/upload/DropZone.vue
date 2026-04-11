<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'file-selected': [file: File]
}>()

const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const ACCEPTED_TYPES = ['.epub', '.pdf', '.mobi']

function handleDrop(e: DragEvent) {
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    emit('file-selected', files[0])
  }
}

function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    emit('file-selected', input.files[0])
  }
}

function openFilePicker() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div
    class="drop-zone"
    :class="{ 'drag-over': isDragOver }"
    @dragover.prevent="isDragOver = true"
    @dragleave="isDragOver = false"
    @drop.prevent="handleDrop"
    @click="openFilePicker"
  >
    <div class="drop-content">
      <div class="drop-icon">📚</div>
      <h3>Drop your book here</h3>
      <p>or click to browse</p>
      <p class="formats">Supports EPUB, PDF, MOBI</p>
    </div>
    <input
      ref="fileInputRef"
      type="file"
      :accept="ACCEPTED_TYPES.join(',')"
      class="file-input"
      @change="handleFileInput"
    />
  </div>
</template>

<style scoped>
.drop-zone { border: 2px dashed var(--color-border, #ddd); border-radius: 0.75rem; padding: 4rem 2rem; text-align: center; cursor: pointer; transition: all 0.2s; }
.drop-zone:hover, .drop-zone.drag-over { border-color: var(--color-primary, #3b82f6); background: var(--color-primary-light, #eff6ff); }
.drop-content { pointer-events: none; }
.drop-icon { font-size: 3rem; margin-bottom: 1rem; }
.drop-content h3 { font-size: 1.125rem; font-weight: 600; margin: 0 0 0.25rem; }
.drop-content p { color: var(--color-text-secondary, #888); font-size: 0.9rem; margin: 0; }
.formats { margin-top: 0.75rem !important; font-size: 0.8rem !important; }
.file-input { display: none; }
</style>
