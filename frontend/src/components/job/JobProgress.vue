<script setup lang="ts">
/**
 * Per-job progress view (T25 / FR-F14).
 *
 * Replaces the wizard's static "Processing started" card. Subscribes to
 * the SSE stream for one job_id and renders the appropriate state:
 *
 *   pending    — "Queued, position 2/3"
 *   running    — section-by-section progress, current section title
 *   cancelling — flashing notice + disabled UI
 *   completed  — success card with link to the book
 *   failed     — error card; reason: cancelled | cli_disappeared | error
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import {
  cancelProcessing,
  connectSSE,
  type ProcessingCompletedPayload,
  type ProcessingFailedPayload,
  type SectionEventPayload,
} from '@/api/processing'
import { useJobQueueStore } from '@/stores/jobQueue'

const props = defineProps<{
  jobId: number
  bookId: number
}>()

const queue = useJobQueueStore()

type Phase = 'pending' | 'running' | 'cancelling' | 'completed' | 'failed'
const phase = ref<Phase>('pending')
const currentSection = ref<{ title: string; index: number; total: number } | null>(null)
const completed = ref<ProcessingCompletedPayload | null>(null)
const failure = ref<ProcessingFailedPayload | null>(null)
const error = ref<string | null>(null)

let source: EventSource | null = null

function connect() {
  source = connectSSE(props.jobId, {
    onJobQueued: () => {
      phase.value = 'pending'
    },
    onJobPromoted: () => {
      phase.value = 'running'
    },
    onJobCancelling: () => {
      phase.value = 'cancelling'
    },
    onProcessingStarted: () => {
      phase.value = 'running'
    },
    onSectionStarted: (data: SectionEventPayload) => {
      phase.value = 'running'
      currentSection.value = {
        title: data.title,
        index: data.index,
        total: data.total,
      }
    },
    onSectionCompleted: (data: SectionEventPayload) => {
      currentSection.value = {
        title: data.title,
        index: data.index,
        total: data.total,
      }
    },
    onProcessingCompleted: (data) => {
      phase.value = 'completed'
      completed.value = data
    },
    onProcessingFailed: (data) => {
      phase.value = 'failed'
      failure.value = data
    },
    onError: () => {
      error.value = 'Connection lost — retrying via the queue indicator.'
    },
  })
}

const queuePosition = computed(() => {
  if (phase.value !== 'pending') return null
  const idx = queue.pendingJobs.findIndex((j) => j.job_id === props.jobId)
  return idx >= 0 ? queue.pendingJobs[idx]!.queue_position : null
})

const failureCopy = computed(() => {
  const f = failure.value
  if (!f) return ''
  const reason = f.reason || 'error'
  if (reason === 'cancelled') return 'Cancelled by user.'
  if (reason === 'cli_disappeared') {
    return 'The LLM CLI became unavailable mid-job. Check your provider in Settings.'
  }
  return f.error || 'Summarization failed.'
})

async function cancel() {
  try {
    await cancelProcessing(props.jobId)
    phase.value = 'cancelling'
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(() => {
  void queue.refresh()
  connect()
})

onUnmounted(() => {
  source?.close()
})
</script>

<template>
  <div
    class="rounded-lg border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-700 dark:bg-stone-800"
    data-testid="job-progress"
    :data-phase="phase"
  >
    <div v-if="phase === 'pending'" class="space-y-2">
      <h3 class="text-base font-semibold text-stone-900 dark:text-stone-100">
        Queued
      </h3>
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Waiting for the queue worker to pick this up.
        <span v-if="queuePosition">Position {{ queuePosition }}.</span>
      </p>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-md border border-stone-300 px-3 py-1 text-sm dark:border-stone-600"
          @click="cancel"
        >
          Cancel
        </button>
      </div>
    </div>

    <div v-else-if="phase === 'running'" class="space-y-2">
      <h3 class="text-base font-semibold text-stone-900 dark:text-stone-100">
        Summarizing…
      </h3>
      <p v-if="currentSection" class="text-sm text-stone-600 dark:text-stone-300">
        {{ currentSection.index + 1 }} / {{ currentSection.total }} —
        <span class="font-medium">{{ currentSection.title }}</span>
      </p>
      <div
        v-if="currentSection"
        class="h-2 w-full overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700"
      >
        <div
          class="h-full bg-blue-500 transition-all"
          :style="{
            width: `${Math.round(
              (100 * (currentSection.index + 1)) / Math.max(1, currentSection.total),
            )}%`,
          }"
        ></div>
      </div>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-md border border-red-300 px-3 py-1 text-sm text-red-700 dark:border-red-700 dark:text-red-300"
          data-testid="job-cancel-btn"
          @click="cancel"
        >
          Cancel
        </button>
      </div>
    </div>

    <div v-else-if="phase === 'cancelling'" class="space-y-2">
      <h3 class="text-base font-semibold text-amber-700 dark:text-amber-300">
        Cancelling…
      </h3>
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Waiting for the active section to stop. Already-summarized sections
        are kept.
      </p>
    </div>

    <div v-else-if="phase === 'completed'" class="space-y-2">
      <h3 class="text-base font-semibold text-emerald-700 dark:text-emerald-300">
        ✓ Done
      </h3>
      <p class="text-sm text-stone-600 dark:text-stone-300">
        {{ completed?.completed ?? 0 }} sections summarized.
        <span v-if="(completed?.failed ?? 0) > 0">
          {{ completed?.failed }} failed.
        </span>
        <span v-if="(completed?.skipped ?? 0) > 0">
          {{ completed?.skipped }} skipped.
        </span>
      </p>
      <div class="flex justify-end">
        <RouterLink
          :to="`/books/${bookId}`"
          class="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Open book
        </RouterLink>
      </div>
    </div>

    <div v-else-if="phase === 'failed'" class="space-y-2">
      <h3 class="text-base font-semibold text-red-700 dark:text-red-300">
        Summarization {{ failure?.reason === 'cancelled' ? 'cancelled' : 'failed' }}
      </h3>
      <p class="text-sm text-stone-600 dark:text-stone-300">{{ failureCopy }}</p>
      <div class="flex justify-end">
        <RouterLink
          :to="`/books/${bookId}`"
          class="rounded-md border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600"
        >
          Open book
        </RouterLink>
      </div>
    </div>

    <p v-if="error" class="mt-2 text-xs text-amber-700 dark:text-amber-300">
      {{ error }}
    </p>
  </div>
</template>
