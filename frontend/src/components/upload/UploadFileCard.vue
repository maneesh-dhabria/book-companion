<script setup lang="ts">
/**
 * UploadFileCard — single-file row for the upload wizard's Step 1.
 *
 * Two-phase indicator (FR-F02):
 *   - phase='uploading' → determinate progress bar driven by uploadProgress
 *   - phase='parsing'   → indeterminate spinner labelled "Parsing"
 *   - phase='error'     → error message + Retry button
 *   - phase='success'   → checkmark
 *
 * The cancel button is enabled only during the upload phase; once parsing
 * starts the request is server-side and not safely cancellable (FR-F03).
 */
import { computed } from 'vue'

type Phase = 'uploading' | 'parsing' | 'error' | 'success'

const props = defineProps<{
  file: File
  phase: Phase
  uploadProgress?: number
  error?: string | null
}>()

defineEmits<{
  cancel: []
  retry: []
}>()

const sizeLabel = computed(() => {
  const kb = props.file.size / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
})

const safePct = computed(() => {
  const v = Number(props.uploadProgress ?? 0)
  if (!Number.isFinite(v)) return 0
  return Math.max(0, Math.min(100, Math.round(v)))
})
</script>

<template>
  <div
    class="rounded-lg border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-700 dark:bg-stone-800"
    data-test="upload-file-card"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="truncate font-medium text-stone-900 dark:text-stone-100">
          {{ file.name }}
        </div>
        <div class="text-sm text-stone-500 dark:text-stone-400">
          {{ sizeLabel }}
        </div>
      </div>
      <button
        v-if="phase !== 'success'"
        :disabled="phase !== 'uploading'"
        class="text-sm text-stone-600 hover:text-stone-900 disabled:cursor-not-allowed disabled:text-stone-300 dark:text-stone-400 dark:hover:text-stone-100"
        data-test="cancel-btn"
        type="button"
        @click="$emit('cancel')"
      >
        Cancel
      </button>
    </div>

    <div v-if="phase === 'uploading'" class="mt-3" data-test="upload-phase">
      <div class="h-2 w-full overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
        <div
          class="h-full bg-stone-900 transition-all dark:bg-stone-100"
          :style="{ width: `${safePct}%` }"
          data-test="upload-progress-bar"
        ></div>
      </div>
      <div class="mt-1 text-xs text-stone-500 dark:text-stone-400">
        Uploading… {{ safePct }}%
      </div>
    </div>

    <div
      v-else-if="phase === 'parsing'"
      class="mt-3 flex items-center gap-2 text-sm text-stone-600 dark:text-stone-300"
      data-test="parse-phase"
    >
      <span
        class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-stone-300 border-t-stone-900 dark:border-stone-600 dark:border-t-stone-100"
        data-test="parse-spinner"
        role="status"
        aria-label="Parsing"
      ></span>
      <span>Parsing the book — this can take a minute…</span>
    </div>

    <div
      v-else-if="phase === 'error'"
      class="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300"
      data-test="error-phase"
    >
      <div class="font-medium">Upload failed</div>
      <div class="mt-1">{{ error || 'An unknown error occurred.' }}</div>
      <button
        type="button"
        class="mt-2 rounded-md bg-red-100 px-3 py-1 text-xs font-medium hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-900/70"
        data-test="retry-btn"
        @click="$emit('retry')"
      >
        Retry
      </button>
    </div>

    <div
      v-else-if="phase === 'success'"
      class="mt-3 text-sm text-emerald-700 dark:text-emerald-400"
      data-test="success-phase"
    >
      ✓ Uploaded
    </div>
  </div>
</template>
