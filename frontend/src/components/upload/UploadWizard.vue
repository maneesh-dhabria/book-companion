<script setup lang="ts">
import { uploadBook } from '@/api/books'
import type { Book } from '@/types'
import DropZone from './DropZone.vue'
import PresetPicker from './PresetPicker.vue'
import StepIndicator from './StepIndicator.vue'
import StructureReview from './StructureReview.vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const currentStep = ref(1)
const bookData = ref<{ id: number; title: string; sections: unknown[] } | null>(null)
const uploadError = ref<string | null>(null)
const uploading = ref(false)
const selectedPreset = ref<string | null>(null)

async function onFileSelected(file: File) {
  // T23 — Metadata step dropped. Upload runs inline from step 1, then we
  // jump straight to Structure review.
  uploading.value = true
  uploadError.value = null
  try {
    const book: Book = await uploadBook(file)
    bookData.value = {
      id: book.id,
      title: book.title,
      sections: book.sections,
    }
    // FR-F3.2 — surface zero-section parse inline before advancing.
    if (!book.sections || book.sections.length === 0) {
      uploadError.value = 'No sections detected in this file.'
      currentStep.value = 1
      return
    }
    currentStep.value = 2
  } catch (e: unknown) {
    uploadError.value = e instanceof Error ? e.message : 'Upload failed'
    currentStep.value = 1
  } finally {
    uploading.value = false
  }
}

function onStructureComplete() {
  currentStep.value = 3
}

function onPresetSelected(preset: string) {
  selectedPreset.value = preset
  currentStep.value = 4
}

function onProcessingStarted() {
  if (bookData.value) {
    router.push(`/books/${bookData.value.id}`)
  }
}

// Four steps — Metadata merged into Upload.
const steps = ['Upload', 'Structure', 'Preset', 'Processing']
</script>

<template>
  <div class="upload-wizard">
    <StepIndicator :steps="steps" :current="currentStep" />

    <div class="wizard-content">
      <DropZone
        v-if="currentStep === 1"
        :uploading="uploading"
        @file-selected="onFileSelected"
      />
      <p
        v-if="currentStep === 1 && uploadError"
        class="error"
        role="alert"
        data-testid="upload-error"
      >
        {{ uploadError }}
      </p>
      <StructureReview
        v-if="currentStep === 2 && bookData"
        :book-id="bookData.id"
        @complete="onStructureComplete"
        @back="currentStep = 1"
      />
      <PresetPicker
        v-else-if="currentStep === 3 && bookData"
        :book-id="bookData.id"
        @select="onPresetSelected"
        @back="currentStep = 2"
      />
      <div v-else-if="currentStep === 4" class="processing-step">
        <h2>Processing Started</h2>
        <p>Your book is being summarized with the "{{ selectedPreset }}" preset.</p>
        <button class="primary-btn" @click="onProcessingStarted">View Progress</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-wizard { max-width: 800px; margin: 0 auto; padding: 2rem; }
.wizard-content { margin-top: 2rem; }
.processing-step { text-align: center; padding: 3rem; }
.processing-step h2 { font-size: 1.25rem; margin-bottom: 0.5rem; }
.primary-btn { margin-top: 1rem; padding: 0.5rem 1.5rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; font-size: 0.9rem; }
.error {
  margin-top: 1rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-danger, #b91c1c);
  color: var(--color-danger, #b91c1c);
  background: var(--color-danger-light, #fef2f2);
  border-radius: 0.375rem;
  font-size: 0.9rem;
}
</style>
