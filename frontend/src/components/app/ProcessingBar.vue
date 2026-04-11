<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  jobs: { jobId: number; bookTitle: string; progress: number; status: string }[]
}>()

const minimized = ref(true)
</script>

<template>
  <div v-if="jobs.length" class="processing-bar" :class="{ minimized }">
    <button class="toggle-btn" @click="minimized = !minimized">
      {{ jobs.length }} active {{ jobs.length === 1 ? 'job' : 'jobs' }}
      {{ minimized ? '▲' : '▼' }}
    </button>
    <div v-if="!minimized" class="job-list">
      <div v-for="job in jobs" :key="job.jobId" class="job-item">
        <span class="job-title">{{ job.bookTitle }}</span>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: job.progress + '%' }" />
        </div>
        <span class="job-status">{{ job.status }}</span>
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
