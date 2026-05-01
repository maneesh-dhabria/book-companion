<script setup lang="ts">
import { computed } from 'vue'
import { useBufferedJobStream } from '@/composables/useBufferedJobStream'

const props = defineProps<{ id: string | number }>()

const jobId = Number(props.id)
const { state, error, isLoading } = useBufferedJobStream(jobId)

const isRunning = computed(
  () => state.value && (state.value.status === 'PENDING' || state.value.status === 'RUNNING'),
)
const isTerminal = computed(
  () =>
    state.value &&
    (state.value.status === 'COMPLETED' ||
      state.value.status === 'FAILED' ||
      state.value.status === 'CANCELLED'),
)

const progressPct = computed(() => {
  if (!state.value) return 0
  const { current, total } = state.value.progress
  if (!total || total <= 0) return 0
  return Math.min(100, Math.round((current / total) * 100))
})

const elapsed = computed(() => {
  if (!state.value?.started_at) return null
  const start = new Date(state.value.started_at).getTime()
  const end = state.value.completed_at
    ? new Date(state.value.completed_at).getTime()
    : Date.now()
  if (Number.isNaN(start) || Number.isNaN(end)) return null
  const sec = Math.max(0, Math.round((end - start) / 1000))
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}m ${s}s`
})

async function onCancel() {
  if (!state.value) return
  state.value.cancelling = true
  try {
    await fetch(`/api/v1/processing/${state.value.id}/cancel`, { method: 'POST' })
  } catch {
    // The job_cancelling SSE will arrive next; if cancel fails network-wise
    // the user can retry from the persistent indicator.
  }
}
</script>

<template>
  <main class="job-progress-view" data-testid="job-progress-view">
    <!-- Loading skeleton (FR-12a) -->
    <div v-if="isLoading" class="state-skeleton" data-testid="job-skeleton">
      <div class="skeleton-title"></div>
      <div class="skeleton-bar"></div>
    </div>

    <!-- 404 / not-found -->
    <div v-else-if="error?.kind === '404'" class="state-not-found">
      <h1>Job not found</h1>
      <p>This job may have been cancelled or expired.</p>
      <router-link :to="{ name: 'library' }" class="btn-primary">Back to Library</router-link>
    </div>

    <!-- Running / pending -->
    <div v-else-if="state && isRunning" class="state-running" data-testid="job-running">
      <h1>Summarizing "{{ state.book_title }}"</h1>
      <div class="progress-bar" role="progressbar" :aria-valuenow="progressPct" :aria-valuemin="0" :aria-valuemax="100">
        <div class="progress-fill" :style="{ width: `${progressPct}%` }"></div>
      </div>
      <div class="progress-meta">
        <span>{{ state.progress.current }} of {{ state.progress.total }} sections</span>
        <span v-if="state.progress.eta_seconds !== null" class="eta">
          · ETA {{ Math.round((state.progress.eta_seconds ?? 0) / 60) }}m
        </span>
      </div>
      <div v-if="state.progress.current_section_title" class="current-section">
        Now: {{ state.progress.current_section_title }}
      </div>
      <div v-if="state.retrying_section_id" class="retry-indicator" data-testid="job-retrying">
        Retrying section {{ state.retrying_section_id }}…
      </div>
      <div v-if="state.cancelling" class="cancelling-banner" data-testid="job-cancelling">
        Cancelling…
      </div>
      <div class="actions">
        <router-link
          :to="{ name: 'book-overview', params: { id: String(state.book_id) } }"
          class="btn-secondary"
        >
          Open Book
        </router-link>
        <button
          v-if="!state.cancelling"
          type="button"
          class="btn-danger"
          @click="onCancel"
          data-testid="job-cancel"
        >
          Cancel
        </button>
      </div>
    </div>

    <!-- Terminal -->
    <div v-else-if="state && isTerminal" class="state-terminal" data-testid="job-terminal">
      <h1>
        <span v-if="state.status === 'COMPLETED'">Summary complete</span>
        <span v-else-if="state.status === 'FAILED'">Summary failed</span>
        <span v-else>Summary cancelled</span>
      </h1>
      <p class="terminal-meta">
        <strong>{{ state.book_title }}</strong>
        <span v-if="elapsed"> · finished in {{ elapsed }}</span>
      </p>
      <ul class="terminal-stats">
        <li>{{ state.progress.current }} of {{ state.progress.total }} sections summarized</li>
        <li v-if="(state.failures ?? 0) > 0">{{ state.failures }} failed</li>
      </ul>
      <p v-if="state.error_message" class="terminal-error">{{ state.error_message }}</p>
      <router-link
        :to="{ name: 'book-overview', params: { id: String(state.book_id) } }"
        class="btn-primary"
      >
        Open Book
      </router-link>
    </div>
  </main>
</template>

<style scoped>
.job-progress-view {
  max-width: 36rem;
  margin: 4rem auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.state-skeleton .skeleton-title {
  height: 1.6rem;
  width: 60%;
  background: var(--color-bg-tertiary);
  border-radius: 4px;
}
.state-skeleton .skeleton-bar {
  height: 0.5rem;
  background: var(--color-bg-tertiary);
  border-radius: 4px;
  margin-top: 0.75rem;
  position: relative;
  overflow: hidden;
}
.state-skeleton .skeleton-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: -40%;
  width: 40%;
  height: 100%;
  background: linear-gradient(90deg, transparent, var(--color-bg-secondary), transparent);
  animation: shimmer 1.2s infinite;
}
@keyframes shimmer {
  to {
    left: 100%;
  }
}
.progress-bar {
  height: 0.5rem;
  background: var(--color-bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--color-accent);
  transition: width 0.2s ease;
}
.progress-meta {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
}
.current-section {
  font-size: 0.95rem;
  color: var(--color-text-primary);
}
.retry-indicator {
  font-size: 0.85rem;
  color: var(--color-warning);
}
.cancelling-banner {
  background: var(--color-bg-tertiary);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
.btn-primary,
.btn-secondary,
.btn-danger {
  display: inline-block;
  padding: 0.45rem 1rem;
  border-radius: 0.25rem;
  text-decoration: none;
  font-size: 0.9rem;
  cursor: pointer;
  border: 1px solid transparent;
}
.btn-primary {
  background: var(--color-accent);
  color: #fff;
}
.btn-secondary {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
.btn-danger {
  background: transparent;
  color: var(--color-error);
  border-color: var(--color-error);
}
.terminal-stats {
  list-style: disc;
  padding-left: 1.25rem;
  font-size: 0.9rem;
  color: var(--color-text-secondary);
}
.terminal-error {
  color: var(--color-error);
  font-size: 0.9rem;
}
</style>
