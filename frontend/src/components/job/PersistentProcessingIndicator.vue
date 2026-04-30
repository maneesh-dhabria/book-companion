<script setup lang="ts">
/**
 * Bottom-bar processing indicator visible across all routes (FR-F18).
 *
 * Shows a compact summary of the running job + pending count; clicking
 * expands an inline list. Hidden when the queue is empty.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useJobQueueStore } from '@/stores/jobQueue'

const router = useRouter()
const queue = useJobQueueStore()
const expanded = ref(false)

const visible = computed(
  () => queue.runningJob !== null || queue.pendingJobs.length > 0,
)

const summaryLine = computed(() => {
  if (queue.runningJob) {
    const pending = queue.pendingJobs.length
    const tail = pending > 0 ? ` (+${pending} queued)` : ''
    return `Summarizing "${queue.runningJob.book_title}"${tail}`
  }
  if (queue.pendingJobs.length > 0) {
    return `${queue.pendingJobs.length} job${queue.pendingJobs.length === 1 ? '' : 's'} queued`
  }
  return ''
})

onMounted(() => queue.startPolling(5000))
onUnmounted(() => queue.stopPolling())

function openRunning() {
  if (queue.runningJob) {
    router.push(`/books/${queue.runningJob.book_id}`)
  }
}

async function cancelJob(jobId: number) {
  await queue.cancel(jobId)
}
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="visible"
      class="fixed inset-x-0 bottom-0 z-40 border-t border-stone-200 bg-white/95 backdrop-blur dark:border-stone-700 dark:bg-stone-900/95"
      data-testid="persistent-processing-indicator"
    >
      <div class="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2">
        <button
          type="button"
          class="flex flex-1 items-center gap-2 text-left text-sm text-stone-900 dark:text-stone-100"
          data-testid="ppi-summary"
          @click="expanded = !expanded"
        >
          <span
            class="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-blue-500"
            aria-hidden="true"
          ></span>
          <span class="truncate">{{ summaryLine }}</span>
        </button>
        <button
          v-if="queue.runningJob"
          type="button"
          class="rounded-md border border-stone-300 px-2 py-1 text-xs hover:bg-stone-50 dark:border-stone-600 dark:hover:bg-stone-800"
          data-testid="ppi-open-running"
          @click="openRunning"
        >
          Open
        </button>
        <router-link
          v-if="queue.runningJob"
          :to="{ name: 'job-detail', params: { id: String(queue.runningJob.job_id) } }"
          class="rounded-md border border-stone-300 px-2 py-1 text-xs hover:bg-stone-50 dark:border-stone-600 dark:hover:bg-stone-800"
          data-testid="ppi-view-details"
        >
          View details
        </router-link>
      </div>
      <div
        v-if="expanded"
        class="border-t border-stone-200 bg-stone-50 px-4 py-2 text-xs dark:border-stone-700 dark:bg-stone-900"
        data-testid="ppi-queue-list"
      >
        <div v-if="queue.runningJob" class="flex items-center justify-between py-1">
          <span class="font-medium">running:</span>
          <span class="flex-1 truncate px-2">{{ queue.runningJob.book_title }}</span>
          <button
            type="button"
            class="text-red-700 hover:underline dark:text-red-300"
            @click="cancelJob(queue.runningJob.job_id)"
          >
            Cancel
          </button>
        </div>
        <div
          v-for="job in queue.pendingJobs"
          :key="job.job_id"
          class="flex items-center justify-between py-1"
        >
          <span class="font-medium">queued #{{ job.queue_position }}:</span>
          <span class="flex-1 truncate px-2">{{ job.book_title }}</span>
          <button
            type="button"
            class="text-red-700 hover:underline dark:text-red-300"
            @click="cancelJob(job.job_id)"
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
