<template>
  <div :data-test="'quiz-tab-root'" :data-mode="mode" class="quiz-tab">
    <!-- E1: No LLM provider available -->
    <div v-if="mode === 'no-llm'" data-test="no-llm-banner" class="quiz-banner quiz-banner-warn">
      {{ COPY.noLLMBanner }}
    </div>

    <!-- E2: No summaries gate -->
    <div
      v-else-if="mode === 'no-summaries'"
      data-test="no-summaries-gate"
      class="quiz-banner quiz-banner-warn"
    >
      {{ COPY.noSummariesGate }}
    </div>

    <!-- FR-19 resume banner -->
    <ResumeBanner
      v-else-if="mode === 'resume' && activeSession"
      :session="activeSession"
      @resume="onResume"
      @stop="onStopAndStart"
    />

    <!-- Active session -->
    <ActiveSession
      v-else-if="mode === 'active'"
      :book-id="bookId"
      :book-slug="bookSlug"
    />

    <!-- Default 'ready' mode: scope picker, themes covered, past-Q&A if any -->
    <template v-else>
      <ScopePicker
        :book-id="bookId"
        :sections="sections"
        :seeded-theme="seededTheme"
        @start="onStartFromScope"
      />
      <ThemesCoveredPanel
        :themes-summary="themesSummary"
        @seed-theme="onSeedTheme"
      />
      <PastQAPanel v-if="pastSessions.length > 0" :sessions="pastSessions" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { COPY } from './copy'
import ScopePicker from './ScopePicker.vue'
import ResumeBanner from './ResumeBanner.vue'
import ActiveSession from './ActiveSession.vue'
import PastQAPanel from './PastQAPanel.vue'
import ThemesCoveredPanel from './ThemesCoveredPanel.vue'
import { getLlmStatus } from '@/api/settings'
import { useQuizSessionsStore } from '@/stores/quizSessions'
import type { QuizScope, QuizSessionListItem, SectionBrief } from '@/types'

type Mode = 'loading' | 'no-llm' | 'no-summaries' | 'resume' | 'active' | 'ready'

const props = withDefaults(
  defineProps<{
    bookId: number
    /** When true, the parent has confirmed at least one section/book summary exists. */
    hasSummaries: boolean
    sections?: SectionBrief[]
    bookSlug?: string
  }>(),
  { sections: () => [], bookSlug: 'book' },
)

const store = useQuizSessionsStore()
const llmAvailable = ref<boolean | null>(null)
const llmLoading = ref(true)

onMounted(async () => {
  // Fetch LLM status and quiz state in parallel.
  const [, llmResult] = await Promise.allSettled([
    store.loadForBook(props.bookId),
    getLlmStatus(),
  ])
  if (llmResult.status === 'fulfilled') {
    llmAvailable.value = !!llmResult.value.preflight.ok
  } else {
    llmAvailable.value = false
  }
  llmLoading.value = false
})

const bookState = computed(() => store.byBook.get(props.bookId) ?? null)
const activeSession = computed(() => bookState.value?.activeSession ?? null)
const pastSessions = computed<QuizSessionListItem[]>(() =>
  (bookState.value?.sessions ?? []).filter((s) => s.status !== 'in_progress'),
)
const currentQuestion = computed(() => bookState.value?.currentQuestion ?? null)
const themesSummary = computed<string | null>(() => bookState.value?.themesSummary ?? null)
const seededTheme = ref<string | null>(null)

function onSeedTheme(value: string) {
  seededTheme.value = value
}

const mode = computed<Mode>(() => {
  if (llmLoading.value || !bookState.value?.loaded) return 'loading'
  if (llmAvailable.value === false) return 'no-llm'
  if (!props.hasSummaries) return 'no-summaries'
  if (activeSession.value && currentQuestion.value) return 'active'
  if (activeSession.value) return 'resume'
  return 'ready'
})

async function onResume() {
  // Phase 5 will implement full resume — for now the mode flips to 'active'
  // once a currentQuestion is materialised; an explicit nextQuestion fetch
  // covers the case where the in-progress session has no cached question.
  if (!activeSession.value) return
  if (!currentQuestion.value) {
    await store.loadNextQuestion(props.bookId)
  }
}

async function onStopAndStart() {
  if (!activeSession.value) return
  // Stub — full stop+pivot flow lives in T28/T33; for now just reload
  // to surface the abandoned session in the past-Q&A list.
  await store.loadForBook(props.bookId)
}

const sections = computed(() => props.sections)

async function onStartFromScope(payload: { scope: QuizScope; theme: string | null }) {
  await store.startSession(props.bookId, payload.scope, payload.theme)
}
</script>

<style scoped>
.quiz-tab {
  padding: 1rem;
}
.quiz-banner {
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}
.quiz-banner-warn {
  background: var(--color-warn-bg, #fff8e1);
  color: var(--color-warn-text, #6b4500);
}
</style>
