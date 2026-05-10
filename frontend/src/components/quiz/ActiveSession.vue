<template>
  <div data-test="active-session" class="active-session">
    <SessionTally
      :session-tally="activeSession ? activeSession.tally : EMPTY_TALLY"
      :lifetime="lifetime"
      :session-skipped="0"
    />

    <WarmUpBanner
      v-if="warmUpActive"
      :missed-concepts="missedConcepts"
      :partial-concepts="partialConcepts"
    />

    <ExplainAffordance
      v-if="currentQuestion"
      :session-id="activeSession!.id"
      :question="currentQuestion"
      @explained="onExplained"
    />

    <LoadingSpinner v-if="loadingQuestion" :copy="COPY.loadingQuestion" />
    <LoadingSpinner v-else-if="loadingGrade" :copy="COPY.loadingGrading" />

    <!-- FR-06: mid-session retry — failures during next-question / submit /
         record-self-assessment surface inline; clicking Retry re-runs the
         failed action without losing session state. -->
    <div
      v-if="store.midSessionError"
      data-testid="mid-session-error"
      class="mid-session-error"
      role="alert"
    >
      <p class="mid-session-error-message">{{ store.midSessionError.message }}</p>
      <button
        type="button"
        data-action="retry"
        class="btn-primary mid-session-error-retry"
        :disabled="midRetrying"
        @click="onMidRetry"
      >
        Retry
      </button>
    </div>

    <QuestionTurn
      v-if="currentQuestion && !loadingQuestion && !loadingGrade"
      :key="currentQuestion.id"
      :question="currentQuestion"
      @submit="onSubmit"
    />

    <FatiguePromptBanner
      v-if="currentQuestion && currentQuestion.feedback"
      :feedback="currentQuestion.feedback"
    />

    <FeedbackPanel
      v-if="currentQuestion && currentQuestion.feedback"
      :feedback="currentQuestion.feedback"
    />

    <div
      v-if="currentQuestion && currentQuestion.feedback && !currentQuestion.self_assessment"
      class="post-answer"
    >
      <SelfAssessmentButtons
        :book-id="bookId"
        :is-first-session="isFirstSession"
        :disabled="false"
      />
      <OverrideAffordance
        :session-id="activeSession!.id"
        :question-id="currentQuestion.id"
      />
    </div>

    <div v-if="currentQuestion" class="turn-controls">
      <SkipButton
        :session-id="activeSession!.id"
        :question-id="currentQuestion.id"
        @skipped="onSkipped"
      />
      <AlreadyAskedLink
        :session-id="activeSession!.id"
        :question-id="currentQuestion.id"
        @discarded="onDiscarded"
      />
      <button
        v-if="currentQuestion.self_assessment"
        type="button"
        data-test="next-question"
        class="btn-primary"
        @click="onNext"
      >
        Next question
      </button>
    </div>

    <SessionEndActions
      v-if="activeSession"
      :session="activeSession"
      :book-slug="bookSlug"
      @stopped="onStopped"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SessionTally from './SessionTally.vue'
import WarmUpBanner from './WarmUpBanner.vue'
import QuestionTurn from './QuestionTurn.vue'
import LoadingSpinner from './LoadingSpinner.vue'
import FeedbackPanel from './FeedbackPanel.vue'
import SelfAssessmentButtons from './SelfAssessmentButtons.vue'
import OverrideAffordance from './OverrideAffordance.vue'
import FatiguePromptBanner from './FatiguePromptBanner.vue'
import ExplainAffordance from './ExplainAffordance.vue'
import SkipButton from './SkipButton.vue'
import AlreadyAskedLink from './AlreadyAskedLink.vue'
import SessionEndActions from './SessionEndActions.vue'
import { COPY } from '@/components/quiz/copy'
import { useQuizSessionsStore } from '@/stores/quizSessions'
import type {
  QuizDiscardResponse,
  QuizExplainResponse,
  QuizSessionListItem,
  QuizSessionTally,
} from '@/types'

const EMPTY_TALLY: QuizSessionTally = {
  got_it: 0,
  partial: 0,
  missed: 0,
  skipped: 0,
  discarded: 0,
}

const props = withDefaults(
  defineProps<{ bookId: number; bookSlug?: string }>(),
  { bookSlug: 'book' },
)

const store = useQuizSessionsStore()

const bookState = computed(() => store.byBook.get(props.bookId) ?? null)
const activeSession = computed<QuizSessionListItem | null>(
  () => bookState.value?.activeSession ?? null,
)
const currentQuestion = computed(() => bookState.value?.currentQuestion ?? null)
const lifetime = computed(
  () =>
    bookState.value?.lifetimeTally ?? {
      total_questions: 0,
      got_it: 0,
      partial: 0,
      missed: 0,
      session_count: 0,
      themes_summary: null,
    },
)
const isFirstSession = computed(() => lifetime.value.session_count === 0)

const loadingQuestion = ref(false)
const loadingGrade = ref(false)
const midRetrying = ref(false)

async function onMidRetry() {
  midRetrying.value = true
  try {
    await store.retryMidSession()
  } catch {
    /* failure repopulates store.midSessionError; user can click again */
  } finally {
    midRetrying.value = false
  }
}

// FR-72: warm-up enumerates Missed/Partial concept_labels from prior sessions.
// Wiring deferred to a follow-up; for now the banner stays hidden by default.
const warmUpActive = computed(() => activeSession.value?.is_warm_up_session ?? false)
const missedConcepts = computed<string[]>(() => [])
const partialConcepts = computed<string[]>(() => [])

async function onSubmit(payload: { user_answer: string }) {
  if (!activeSession.value || !currentQuestion.value) return
  loadingGrade.value = true
  try {
    await store.submitAnswer(props.bookId, payload.user_answer)
  } finally {
    loadingGrade.value = false
  }
}

async function onSkipped() {
  if (!activeSession.value) return
  loadingQuestion.value = true
  try {
    await store.loadNextQuestion(props.bookId)
  } finally {
    loadingQuestion.value = false
  }
}

async function onNext() {
  if (!activeSession.value) return
  loadingQuestion.value = true
  try {
    await store.loadNextQuestion(props.bookId)
  } finally {
    loadingQuestion.value = false
  }
}

function onDiscarded(resp: QuizDiscardResponse) {
  // Replace the current question with the replacement returned by /discard.
  const state = store.byBook.get(props.bookId)
  if (state) state.currentQuestion = resp.replacement
}

async function onExplained(_resp: QuizExplainResponse) {
  // Reload session detail so explain_history is refreshed on the current row.
  await store.reloadActiveSession(props.bookId)
}

async function onStopped(_session: QuizSessionListItem) {
  // After Stop, reload the book so QuizTab flips back to the scope picker.
  await store.loadForBook(props.bookId)
}
</script>

<style scoped>
.active-session {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1rem;
}
.post-answer {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.mid-session-error {
  border: 1px solid rgba(244, 63, 94, 0.4);
  background: rgba(254, 226, 226, 0.6);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.mid-session-error-message {
  margin: 0;
  color: #7f1d1d;
  font-size: 0.875rem;
}
.mid-session-error-retry {
  align-self: flex-start;
  margin-left: 0;
}
.turn-controls {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  justify-content: flex-start;
  padding-top: 0.5rem;
  border-top: 1px solid #e5e7eb;
}
.btn-primary {
  margin-left: auto;
  padding: 0.45rem 1rem;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}
</style>
