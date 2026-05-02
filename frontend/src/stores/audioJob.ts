import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type AudioJobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'

export interface AudioJob {
  id: number
  status: AudioJobStatus
  completed: number
  total: number
  current_kind?: string | null
  current_ref?: string | null
  already_stale?: number
}

export interface AudioJobEvent {
  type: string
  job_id?: number
  completed?: number
  total?: number
  current_kind?: string | null
  current_ref?: string | null
  already_stale?: number
  status?: AudioJobStatus
  last_event_at?: number
}

export const useAudioJobStore = defineStore('audioJob', () => {
  const activeJob = ref<AudioJob | null>(null)
  const lastEventAt = ref<number>(0)

  const isRunning = computed(
    () => activeJob.value?.status === 'RUNNING' || activeJob.value?.status === 'PENDING',
  )

  function apply(event: AudioJobEvent) {
    if (typeof event.last_event_at === 'number') {
      lastEventAt.value = event.last_event_at
    }
    if (!activeJob.value && event.job_id) {
      activeJob.value = {
        id: event.job_id,
        status: event.status ?? 'RUNNING',
        completed: event.completed ?? 0,
        total: event.total ?? 0,
        already_stale: event.already_stale ?? 0,
      }
      return
    }
    if (!activeJob.value) return
    if (typeof event.completed === 'number') activeJob.value.completed = event.completed
    if (typeof event.total === 'number') activeJob.value.total = event.total
    if (event.current_kind !== undefined) activeJob.value.current_kind = event.current_kind
    if (event.current_ref !== undefined) activeJob.value.current_ref = event.current_ref
    if (typeof event.already_stale === 'number')
      activeJob.value.already_stale = event.already_stale
    if (event.status) activeJob.value.status = event.status
    if (event.type === 'job_completed' || event.type === 'job_failed' || event.type === 'job_cancelled') {
      if (activeJob.value.status === 'COMPLETED' || activeJob.value.status === 'FAILED' || activeJob.value.status === 'CANCELLED') {
        // job finished — keep brief tombstone for UI, callers can clear()
      }
    }
  }

  function clear() {
    activeJob.value = null
    lastEventAt.value = 0
  }

  function setActiveJob(job: AudioJob | null) {
    activeJob.value = job
  }

  return { activeJob, lastEventAt, isRunning, apply, clear, setActiveJob }
})
