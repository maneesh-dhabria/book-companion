<script setup lang="ts">
import { computed, ref } from 'vue'

interface AudioJob {
  jobId: number
  step: 'audio'
  completed: number
  total: number
  current_kind?: string | null
  current_ref?: string | null
  already_stale?: number
}

const props = withDefaults(
  defineProps<{
    jobs: { jobId: number; bookTitle: string; progress: number; status: string }[]
    audioJob?: AudioJob | null
  }>(),
  { audioJob: null },
)

const minimized = ref(true)
const hasAny = computed(() => props.jobs.length > 0 || props.audioJob)
const audioPct = computed(() =>
  props.audioJob && props.audioJob.total > 0
    ? Math.round((props.audioJob.completed / props.audioJob.total) * 100)
    : 0,
)
</script>

<template>
  <div v-if="hasAny" class="processing-bar" :class="{ minimized }">
    <button class="toggle-btn" @click="minimized = !minimized">
      <template v-if="audioJob && jobs.length === 0">Generating audio</template>
      <template v-else>{{ jobs.length }} active {{ jobs.length === 1 ? 'job' : 'jobs' }}</template>
      {{ minimized ? '▲' : '▼' }}
    </button>
    <div v-if="!minimized || audioJob" class="job-list">
      <div v-for="job in jobs" :key="job.jobId" class="job-item">
        <span class="job-title">{{ job.bookTitle }}</span>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: job.progress + '%' }" />
        </div>
        <span class="job-status">{{ job.status }}</span>
      </div>
      <div v-if="audioJob" class="job-item" data-testid="audio-job">
        <span class="job-title">Generating audio</span>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: audioPct + '%' }" />
        </div>
        <span class="job-status">
          {{ audioJob.completed }} / {{ audioJob.total }}
          <template v-if="audioJob.already_stale">
            · {{ audioJob.already_stale }} already stale
          </template>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.processing-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--color-bg, #fff); border-top: 1px solid var(--color-border, #e0e0e0); z-index: 50; }
.toggle-btn { width: 100%; padding: 0.5rem; background: none; border: none; cursor: pointer; font-size: 0.8rem; color: var(--color-text-secondary, #666); }
.job-list { padding: 0 0.75rem 0.75rem; }
.job-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.375rem 0; }
.job-title { font-size: 0.8rem; min-width: 120px; }
.progress-bar { flex: 1; height: 6px; background: var(--color-bg-secondary, #e5e7eb); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--color-primary, #3b82f6); border-radius: 3px; transition: width 0.3s; }
.job-status { font-size: 0.7rem; color: var(--color-text-secondary, #888); min-width: 60px; text-align: right; }
</style>
