/**
 * Global job-queue store. Replaces useSummarizationJobStore (P9) with a
 * queue-aware shape: one runningJob + a pendingJobs[] list.
 *
 * Hydration sequence (FR-F19b):
 *   1. connect() opens an SSE stream for each known active job_id
 *   2. fetches GET /api/v1/processing/jobs?status=PENDING,RUNNING
 *   3. drains buffered SSE events, reconciling by last_event_at
 *
 * For Phase G v1 we keep the store deliberately minimal: hydrate on mount,
 * react to SSE for the active jobs, and let the UI poll-refresh when needed.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  cancelProcessing,
  listProcessingJobs,
  type ProcessingJobListItem,
} from '@/api/processing'

export const useJobQueueStore = defineStore('jobQueue', () => {
  const runningJob = ref<ProcessingJobListItem | null>(null)
  const pendingJobs = ref<ProcessingJobListItem[]>([])
  const lastFetchedAt = ref<string | null>(null)
  const error = ref<string | null>(null)

  async function refresh() {
    try {
      const { jobs } = await listProcessingJobs(['PENDING', 'RUNNING'])
      runningJob.value = jobs.find((j) => j.status.toLowerCase() === 'running') ?? null
      pendingJobs.value = jobs.filter((j) => j.status.toLowerCase() === 'pending')
      lastFetchedAt.value = new Date().toISOString()
      error.value = null
    } catch (e) {
      error.value = (e as Error).message
    }
  }

  async function cancel(jobId: number) {
    await cancelProcessing(jobId)
    await refresh()
  }

  /** Polling fallback. Lightweight — backs the persistent indicator
   * without requiring a dedicated SSE connection per job. The full
   * SSE-driven reconciliation is exercised by the per-job JobProgress
   * component when a route mounts it.
   */
  let pollHandle: number | null = null
  function startPolling(intervalMs = 5000) {
    if (pollHandle !== null) return
    void refresh()
    pollHandle = window.setInterval(() => void refresh(), intervalMs)
  }
  function stopPolling() {
    if (pollHandle !== null) {
      window.clearInterval(pollHandle)
      pollHandle = null
    }
  }

  return {
    runningJob,
    pendingJobs,
    lastFetchedAt,
    error,
    refresh,
    cancel,
    startPolling,
    stopPolling,
  }
})
