<script setup lang="ts">
import { computed, ref } from 'vue'

import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { useUiStore } from '@/stores/ui'

// FR-F2.x — tri-state summary progress:
//   pending  → "{n} sections pending" + Summarize button
//   failures → "{k} failed, {n} pending" + Retry button (orange badge)
//   complete → green checkmark "All sections summarized"
// FR-F2.5: while the POST is in flight (between click and the first SSE
// event landing) the button shows an inline spinner and is disabled.
const props = defineProps<{
  bookId: number
  summarized: number
  total: number
  failedAndPending?: number
}>()

const job = useSummarizationJobStore()
const isActive = computed(() => job.isActive)
const failed = computed(() => props.failedAndPending ?? 0)
const pending = computed(() =>
  Math.max(0, props.total - props.summarized - failed.value),
)

const state = computed<'pending' | 'failures' | 'complete'>(() => {
  if (props.summarized >= props.total) return 'complete'
  if (failed.value > 0) return 'failures'
  return 'pending'
})

const starting = ref(false)

async function onClick() {
  starting.value = true
  try {
    await job.startJob(props.bookId, {
      scope: state.value === 'failures' ? 'failed' : 'pending',
    })
  } catch (e) {
    useUiStore().showToast(
      `Couldn't start summarization: ${(e as Error).message}`,
      'error',
    )
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div v-if="total > 0" class="summary-progress" :class="`state-${state}`">
    <template v-if="state === 'complete'">
      <span class="badge complete" aria-label="All sections summarized">✓</span>
      <span>All {{ total }} sections summarized</span>
    </template>
    <template v-else-if="state === 'failures'">
      <span class="badge failures" aria-label="Some sections failed">!</span>
      <span>
        {{ failed }} failed, {{ pending }} pending ({{ summarized }}/{{ total }} done)
      </span>
      <button
        class="btn retry"
        :disabled="isActive || starting"
        @click="onClick"
      >
        <span v-if="starting" class="inline-spinner" aria-hidden="true" />
        {{ isActive ? `Retrying… ${summarized}/${total}` : 'Retry failed sections' }}
      </button>
    </template>
    <template v-else>
      <span>{{ summarized }} of {{ total }} sections summarized</span>
      <button
        class="btn"
        :disabled="isActive || starting"
        @click="onClick"
      >
        <span v-if="starting" class="inline-spinner" aria-hidden="true" />
        {{ isActive ? `Summarizing… ${summarized}/${total}` : 'Summarize pending sections' }}
      </button>
    </template>
  </div>
</template>

<style scoped>
.summary-progress {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  color: var(--color-text-muted);
  padding: 8px 0;
}

.state-complete {
  color: #059669;
}

.state-failures {
  color: #b45309;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  color: white;
}

.badge.complete {
  background: #059669;
}

.badge.failures {
  background: #f59e0b;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  cursor: pointer;
}

.btn.retry {
  border-color: #f59e0b;
  color: #b45309;
}

.btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.inline-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(0, 0, 0, 0.18);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: sp-spin 0.8s linear infinite;
}

@keyframes sp-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .inline-spinner {
    animation: none;
    border-top-color: rgba(0, 0, 0, 0.55);
  }
}
</style>
