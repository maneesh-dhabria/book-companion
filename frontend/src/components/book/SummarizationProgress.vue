<script setup lang="ts">
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { computed } from 'vue'

const props = defineProps<{ bookId: number; summarized: number; total: number }>()

const job = useSummarizationJobStore()
const isActive = computed(() => job.isActive)
const showButton = computed(() => props.summarized < props.total)

async function onClick() {
  await job.startJob(props.bookId, { scope: 'pending' })
}
</script>

<template>
  <div v-if="total > 0" class="summary-progress">
    <span>{{ summarized }} of {{ total }} sections summarized</span>
    <button v-if="showButton" class="btn" :disabled="isActive" @click="onClick">
      {{ isActive ? `Summarizing… ${summarized}/${total}` : 'Summarize pending sections' }}
    </button>
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

.btn {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
