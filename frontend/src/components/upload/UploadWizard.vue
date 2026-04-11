<script setup lang="ts">
import DropZone from './DropZone.vue'
import MetadataForm from './MetadataForm.vue'
import PresetPicker from './PresetPicker.vue'
import StepIndicator from './StepIndicator.vue'
import StructureReview from './StructureReview.vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const currentStep = ref(1)
const uploadedFile = ref<File | null>(null)
const bookData = ref<{ id: number; title: string; sections: unknown[] } | null>(null)
const selectedPreset = ref('balanced')

function onFileSelected(file: File) {
  uploadedFile.value = file
  currentStep.value = 2
}

function onMetadataComplete(data: { id: number; title: string; sections: unknown[] }) {
  bookData.value = data
  currentStep.value = 3
}

function onStructureComplete() {
  currentStep.value = 4
}

function onPresetSelected(preset: string) {
  selectedPreset.value = preset
  currentStep.value = 5
}

function onProcessingStarted() {
  // Navigate to book detail to see progress
  if (bookData.value) {
    router.push(`/books/${bookData.value.id}`)
  }
}

const steps = ['Upload', 'Metadata', 'Structure', 'Preset', 'Processing']
</script>

<template>
  <div class="upload-wizard">
    <StepIndicator :steps="steps" :current="currentStep" />

    <div class="wizard-content">
      <DropZone v-if="currentStep === 1" @file-selected="onFileSelected" />
      <MetadataForm
        v-else-if="currentStep === 2"
        :file="uploadedFile!"
        @complete="onMetadataComplete"
        @back="currentStep = 1"
      />
      <StructureReview
        v-else-if="currentStep === 3 && bookData"
        :book-id="bookData.id"
        @complete="onStructureComplete"
        @back="currentStep = 2"
      />
      <PresetPicker
        v-else-if="currentStep === 4 && bookData"
        :book-id="bookData.id"
        @select="onPresetSelected"
        @back="currentStep = 3"
      />
      <div v-else-if="currentStep === 5" class="processing-step">
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
</style>
