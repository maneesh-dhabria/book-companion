<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'

interface SectionLike {
  id: number
  order_index?: number
  has_summary?: boolean
  default_summary?: { id?: number } | null
  default_summary_id?: number | null
  summary_id?: number | null
}

interface BookLike {
  id: number
  sections?: SectionLike[]
  default_summary?: { summary_md?: string; generated_at?: string; created_at?: string } | null
  last_summary_failure?: { code?: string; stderr?: string; at?: string } | null
}

const props = defineProps<{
  book: BookLike
  defaultPreset?: string
}>()

const emit = defineEmits<{
  'book-refetch': []
}>()

const router = useRouter()

const summarizedCount = computed(
  () =>
    (props.book.sections || []).filter(
      (s) => s.has_summary || s.default_summary_id || s.default_summary || s.summary_id,
    ).length,
)
const totalCount = computed(() => (props.book.sections || []).length)

const activeJobId = ref<number | null>(null)
const sse = ref<EventSource | null>(null)
const errorMsg = ref<string | null>(null)

const state = computed<'populated' | 'inProgress' | 'failed' | 'empty'>(() => {
  if (props.book.default_summary && props.book.default_summary.summary_md) return 'populated'
  if (activeJobId.value !== null) return 'inProgress'
  if (props.book.last_summary_failure && !props.book.default_summary) return 'failed'
  return 'empty'
})

function attachSse(jobId: number) {
  detachSse()
  activeJobId.value = jobId
  try {
    const es = new EventSource(`/api/v1/processing/${jobId}/stream`)
    sse.value = es
    es.addEventListener('processing_completed', () => {
      detachSse()
      emit('book-refetch')
    })
    es.addEventListener('processing_failed', () => {
      detachSse()
      emit('book-refetch')
    })
    es.addEventListener('job_cancelling', () => {
      detachSse()
      emit('book-refetch')
    })
    es.onerror = () => {
      // Connection lost; let parent re-fetch and we'll re-evaluate.
      detachSse()
      emit('book-refetch')
    }
  } catch {
    // EventSource unavailable in some test environments; ignore.
  }
}

function detachSse() {
  if (sse.value) {
    sse.value.close()
    sse.value = null
  }
  activeJobId.value = null
}

onUnmounted(detachSse)

async function startGenerate() {
  errorMsg.value = null
  try {
    const r = await fetch(`/api/v1/books/${props.book.id}/book-summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset_name: props.defaultPreset || 'practitioner_bullets' }),
    })
    if (r.status === 201 || r.status === 202) {
      const body = await r.json()
      const jobId = body.job_id ?? body.id
      if (typeof jobId === 'number') attachSse(jobId)
    } else if (r.status === 409) {
      const body = await r.json().catch(() => ({}) as Record<string, unknown>)
      const aj = (body as { active_job_id?: number }).active_job_id
      if (typeof aj === 'number') attachSse(aj)
    } else {
      const body = await r.json().catch(() => ({}) as Record<string, unknown>)
      errorMsg.value =
        (body as { detail?: string }).detail || `Request failed (${r.status})`
    }
  } catch (e) {
    errorMsg.value = (e as Error).message
  }
}

async function cancelJob() {
  if (activeJobId.value === null) return
  try {
    await fetch(`/api/v1/processing/${activeJobId.value}/cancel`, { method: 'POST' })
  } finally {
    detachSse()
    emit('book-refetch')
  }
}

function readSectionSummaries() {
  const sections = (props.book.sections || []).slice()
  if (sections.length === 0) return
  sections.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
  const first = sections[0]
  router.push({
    path: `/books/${props.book.id}/sections/${first.id}`,
    query: { tab: 'summary' },
  })
}

watch(
  () => props.book.id,
  () => {
    detachSse()
    errorMsg.value = null
  },
)
</script>

<template>
  <div class="book-summary-tab">
    <template v-if="state === 'populated'">
      <header class="book-summary-tab__header">
        <h2>Book Summary</h2>
        <div class="book-summary-tab__actions">
          <button class="btn-secondary" type="button" @click="readSectionSummaries">
            Read Section Summaries
          </button>
          <button class="btn-secondary regenerate-cta" type="button" @click="startGenerate">
            Regenerate
          </button>
        </div>
      </header>
      <MarkdownRenderer :content="book.default_summary!.summary_md!" />
    </template>

    <template v-else-if="state === 'inProgress'">
      <div class="book-summary-tab__progress">
        <p>Generating book summary…</p>
        <button class="btn-secondary" type="button" @click="cancelJob">Cancel</button>
      </div>
    </template>

    <template v-else-if="state === 'failed'">
      <div class="book-summary-tab__failed">
        <h3>Last attempt failed</h3>
        <p class="error-msg">{{ book.last_summary_failure?.stderr || book.last_summary_failure?.code }}</p>
        <button class="btn-primary retry-cta" type="button" @click="startGenerate">
          Retry
        </button>
      </div>
    </template>

    <template v-else>
      <div class="book-summary-tab__empty">
        <p v-if="summarizedCount === 0" class="empty-hint">
          Summarize at least one section first, then come back to generate the book summary.
        </p>
        <p v-else class="empty-progress">
          {{ summarizedCount }} of {{ totalCount }} sections summarized.
        </p>
        <button
          class="btn-primary generate-cta"
          type="button"
          :disabled="summarizedCount === 0"
          @click="startGenerate"
        >
          Generate book summary
        </button>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.book-summary-tab {
  padding: 12px 0 64px;
}
.book-summary-tab__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}
.book-summary-tab__actions {
  display: flex;
  gap: 8px;
}
.book-summary-tab__empty,
.book-summary-tab__failed,
.book-summary-tab__progress {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 24px;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
}
.error-msg {
  color: var(--color-text-danger, #b91c1c);
  font-size: 0.95em;
}
.btn-primary,
.btn-secondary {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  cursor: pointer;
  font-size: 14px;
}
.btn-primary {
  background: var(--color-accent, #4f46e5);
  color: var(--color-text-on-accent, white);
  border-color: transparent;
}
.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
