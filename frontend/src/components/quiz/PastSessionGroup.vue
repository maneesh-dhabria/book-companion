<template>
  <div data-test="past-session-group" class="group">
    <button
      type="button"
      data-test="past-session-toggle"
      class="header"
      :aria-expanded="expanded"
      @click="onToggle"
    >
      <span class="caret">{{ expanded ? '▼' : '▶' }}</span>
      <span class="title">Session #{{ session.id }}</span>
      <span class="meta">
        {{ formattedDate }} · {{ session.question_count }} q ·
        {{ session.tally.got_it }} / {{ session.tally.partial }} / {{ session.tally.missed }}
      </span>
      <span v-if="session.is_warm_up_session" class="badge">warm-up</span>
    </button>

    <div v-if="expanded" class="body">
      <p v-if="loading" class="loading">Loading…</p>
      <p v-else-if="error" class="error">Couldn't load — {{ error }}</p>
      <ul v-else-if="questions.length > 0" class="rows">
        <PastQuestionRow v-for="q in questions" :key="q.id" :question="q" />
      </ul>
      <p v-else class="empty">No questions in this session.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PastQuestionRow from './PastQuestionRow.vue'
import { getSession } from '@/api/quizSessions'
import type { QuizQuestion, QuizSessionListItem } from '@/types'

const props = defineProps<{
  session: QuizSessionListItem
  defaultExpanded: boolean
}>()

const expanded = ref(props.defaultExpanded)
const questions = ref<QuizQuestion[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref<string | null>(null)

const formattedDate = computed(() => {
  try {
    return new Date(props.session.created_at).toLocaleDateString()
  } catch {
    return props.session.created_at
  }
})

async function load() {
  if (loaded.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    const detail = await getSession(props.session.id)
    questions.value = detail.questions
    loaded.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function onToggle() {
  expanded.value = !expanded.value
}

watch(expanded, (v) => {
  if (v) load()
}, { immediate: true })
</script>

<style scoped>
.group {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem 0.85rem;
  background: white;
  border: none;
  cursor: pointer;
  text-align: left;
  font-size: 0.9rem;
}
.header:hover {
  background: #f9fafb;
}
.caret {
  color: #6b7280;
  font-size: 0.75rem;
  width: 0.85rem;
}
.title {
  font-weight: 600;
  color: #111827;
}
.meta {
  font-size: 0.78rem;
  color: #6b7280;
}
.badge {
  margin-left: auto;
  font-size: 0.68rem;
  background: #dbeafe;
  color: #1e40af;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  text-transform: uppercase;
  font-weight: 500;
}
.body {
  padding: 0.6rem;
  background: #fafafa;
  border-top: 1px solid #e5e7eb;
}
.loading,
.error,
.empty {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
}
.error {
  color: #b91c1c;
}
.rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
</style>
