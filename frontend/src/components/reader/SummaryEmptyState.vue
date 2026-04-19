<script setup lang="ts">
import { FRONT_MATTER_TYPES } from '@/stores/reader'
import { computed } from 'vue'

const props = defineProps<{
  section: { id: number; title: string; section_type: string }
  activeJobSectionId: number | null
  failedError: string | null
}>()
const emit = defineEmits<{ summarize: [] }>()

const isFrontMatter = computed(() => FRONT_MATTER_TYPES.has(props.section.section_type))
const isGenerating = computed(() => props.activeJobSectionId === props.section.id)
const hasFailed = computed(() => !!props.failedError && !isGenerating.value)
</script>

<template>
  <div class="summary-empty">
    <template v-if="isFrontMatter">
      <p class="muted">Summary not applicable for {{ section.title }}</p>
    </template>
    <template v-else-if="isGenerating">
      <p class="muted">Generating summary… <span class="spinner" /></p>
    </template>
    <template v-else-if="hasFailed">
      <p class="error">Summary generation failed: {{ failedError }}</p>
      <button class="btn" @click="emit('summarize')">Retry</button>
    </template>
    <template v-else>
      <h3>Not yet summarized</h3>
      <p class="muted">This section doesn't have a summary yet.</p>
      <button class="btn primary" @click="emit('summarize')">
        Summarize this section
      </button>
    </template>
  </div>
</template>

<style scoped>
.summary-empty {
  padding: 48px 24px;
  text-align: center;
  max-width: 480px;
  margin: 0 auto;
}

.muted {
  color: var(--color-text-muted);
}

.error {
  color: var(--color-danger, #c0392b);
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  cursor: pointer;
}

.btn.primary {
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-left: 4px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
