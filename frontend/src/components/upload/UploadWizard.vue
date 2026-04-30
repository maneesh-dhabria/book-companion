<script setup lang="ts">
/**
 * Upload wizard, v1.6 (T23 / FR-F2..F17).
 *
 * Steps:
 *   1. Upload  — DropZone + UploadFileCard (XHR progress, cancellable)
 *   2. Structure — StructureEditor in 'wizard' mode (no edit-impact dialog
 *      because no summary exists yet)
 *   3. Preset  — existing PresetPicker. Start button disabled until preflight passes.
 *   4. Processing — JobProgress (no auto-redirect; user clicks "Open book"
 *      when ready).
 */
import { computed, onMounted, ref } from 'vue'

import { uploadBookWithProgress } from '@/api/books'
import {
  getLlmStatus,
  type LLMStatusResponse,
} from '@/api/settings'
import type { Book } from '@/types'

import DropZone from './DropZone.vue'
import PresetPicker from './PresetPicker.vue'
import StepIndicator from './StepIndicator.vue'
import StructureEditor from './StructureEditor.vue'
import UploadFileCard from './UploadFileCard.vue'
import JobProgress from '@/components/job/JobProgress.vue'

const currentStep = ref(1)
const bookData = ref<{ id: number; title: string } | null>(null)
const llmStatus = ref<LLMStatusResponse | null>(null)
const startError = ref<string | null>(null)

// ─ Step 1 — upload state ────────────────────────────────────────────────
type UploadPhase = 'idle' | 'uploading' | 'parsing' | 'error' | 'success'
const phase = ref<UploadPhase>('idle')
const file = ref<File | null>(null)
const uploadProgress = ref(0)
const uploadError = ref<string | null>(null)
let uploadController: AbortController | null = null

async function onFileSelected(picked: File) {
  file.value = picked
  uploadProgress.value = 0
  uploadError.value = null
  phase.value = 'uploading'
  uploadController = new AbortController()
  try {
    const book = await uploadBookWithProgress(
      picked,
      (pct) => {
        uploadProgress.value = pct
        if (pct >= 100) phase.value = 'parsing'
      },
      uploadController.signal,
    )
    bookData.value = { id: (book as Book).id, title: (book as Book).title }
    if (!(book as Book).sections || (book as Book).sections.length === 0) {
      uploadError.value = 'No sections detected in this file.'
      phase.value = 'error'
      return
    }
    phase.value = 'success'
    currentStep.value = 2
  } catch (e) {
    if ((e as Error).message === 'Cancelled') {
      phase.value = 'idle'
      file.value = null
      return
    }
    uploadError.value = (e as Error).message
    phase.value = 'error'
  } finally {
    uploadController = null
  }
}

function cancelUpload() {
  uploadController?.abort()
}

function retryUpload() {
  if (file.value) {
    void onFileSelected(file.value)
  } else {
    phase.value = 'idle'
  }
}

// ─ Step 3 — preset selection + preflight gate ────────────────────────────
const selectedPreset = ref<string | null>(null)
const preflightOk = computed(
  () => llmStatus.value?.preflight?.binary_resolved === true,
)
const preflightReason = computed(
  () => llmStatus.value?.preflight?.reason ?? null,
)

async function loadPreflight() {
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
}

onMounted(loadPreflight)

function onPresetStarted(payload: { preset: string; jobId: number }) {
  selectedPreset.value = payload.preset
  jobId.value = payload.jobId
  startError.value = null
  currentStep.value = 4
}

// ─ Step 4 ────────────────────────────────────────────────────────────────
const jobId = ref<number | null>(null)

const steps = ['Upload', 'Structure', 'Preset', 'Processing']
</script>

<template>
  <div class="upload-wizard mx-auto max-w-3xl px-4 py-6">
    <StepIndicator :steps="steps" :current="currentStep" />

    <div class="mt-6">
      <!-- Step 1 — Upload -->
      <div v-if="currentStep === 1" class="space-y-4">
        <DropZone
          v-if="phase === 'idle'"
          :uploading="false"
          @file-selected="onFileSelected"
        />
        <UploadFileCard
          v-else-if="file"
          :file="file"
          :phase="phase === 'success' ? 'success' : phase === 'error' ? 'error' : phase"
          :upload-progress="uploadProgress"
          :error="uploadError"
          @cancel="cancelUpload"
          @retry="retryUpload"
        />
      </div>

      <!-- Step 2 — Structure -->
      <StructureEditor
        v-else-if="currentStep === 2 && bookData"
        :book-id="bookData.id"
        mode="wizard"
        @complete="currentStep = 3"
        @back="currentStep = 1"
      />

      <!-- Step 3 — Preset -->
      <div v-else-if="currentStep === 3 && bookData" class="space-y-4">
        <div
          v-if="!preflightOk"
          class="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200"
          data-testid="step3-preflight-banner"
        >
          {{
            preflightReason ||
            'LLM CLI status unknown. Check Settings before starting.'
          }}
        </div>
        <PresetPicker
          :book-id="bookData.id"
          :start-disabled="!preflightOk"
          @started="onPresetStarted"
          @back="currentStep = 2"
        />
        <p
          v-if="startError"
          class="rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300"
          data-testid="start-error"
        >
          {{ startError }}
        </p>
      </div>

      <!-- Step 4 — Processing -->
      <JobProgress
        v-else-if="currentStep === 4 && bookData && jobId"
        :job-id="jobId"
        :book-id="bookData.id"
      />
    </div>
  </div>
</template>
