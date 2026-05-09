<template>
  <div data-test="question-turn" class="question-turn">
    <!-- Citation chip alongside question for `open`; or after-answer for mcq/spot_error (FR-41). -->
    <div v-if="citationVisible" class="citation-row">
      <CitationChip :book-id="question.book_id" :citation="question.citation" />
    </div>

    <h3 data-test="question-stem" class="stem">{{ question.stem }}</h3>

    <div class="input-area">
      <McqInput
        v-if="question.shape === 'mcq' && question.mcq_options"
        :options="question.mcq_options"
        :selected-index="mcqIndex"
        @select="onMcqSelect"
      />
      <OpenInput
        v-else-if="question.shape === 'open'"
        v-model="openAnswer"
      />
      <SpotErrorInput
        v-else-if="question.shape === 'spot_error'"
        :intended-error="question.intended_error || ''"
        v-model="correction"
      />
    </div>

    <div class="actions">
      <button
        type="button"
        data-test="submit"
        class="btn-primary"
        :disabled="!canSubmit || submitting"
        @click="onSubmit"
      >
        Submit
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import McqInput from './McqInput.vue'
import OpenInput from './OpenInput.vue'
import SpotErrorInput from './SpotErrorInput.vue'
import CitationChip from './CitationChip.vue'
import type { QuizQuestion } from '@/types'

const props = defineProps<{ question: QuizQuestion }>()
const emit = defineEmits<{
  (e: 'submit', payload: { user_answer: string }): void
}>()

const mcqIndex = ref<number | null>(null)
const openAnswer = ref('')
const correction = ref('')
const submitting = ref(false)
let fallbackTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.question.id,
  () => {
    mcqIndex.value = null
    openAnswer.value = ''
    correction.value = ''
    submitting.value = false
    if (fallbackTimer) {
      clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
  },
)

const citationVisible = computed(() => {
  if (props.question.shape === 'open') return true
  // For mcq / spot_error: hide until after-answer (feedback present, FR-41).
  return props.question.feedback != null
})

const canSubmit = computed(() => {
  switch (props.question.shape) {
    case 'mcq':
      return mcqIndex.value !== null
    case 'open':
      return openAnswer.value.trim().length >= 1
    case 'spot_error':
      return correction.value.trim().length >= 1
    default:
      return false
  }
})

function onMcqSelect(idx: number) {
  mcqIndex.value = idx
}

function onSubmit() {
  if (!canSubmit.value || submitting.value) return
  let user_answer = ''
  if (props.question.shape === 'mcq' && mcqIndex.value !== null) {
    user_answer = props.question.mcq_options?.[mcqIndex.value] ?? ''
  } else if (props.question.shape === 'open') {
    user_answer = openAnswer.value
  } else if (props.question.shape === 'spot_error') {
    user_answer = correction.value
  }
  submitting.value = true
  // FR-49: 5-second fallback re-enable so a hung subprocess doesn't lock the UI.
  fallbackTimer = setTimeout(() => {
    submitting.value = false
    fallbackTimer = null
  }, 5000)
  emit('submit', { user_answer })
}

defineExpose({ canSubmit, submitting })
</script>

<style scoped>
.question-turn {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.citation-row {
  display: flex;
}
.stem {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #111827;
}
.input-area {
  display: flex;
  flex-direction: column;
}
.actions {
  display: flex;
  justify-content: flex-end;
}
.btn-primary {
  padding: 0.5rem 1.1rem;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}
.btn-primary:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}
</style>
