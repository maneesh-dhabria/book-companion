<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import TtsPlayButton from '@/components/audio/TtsPlayButton.vue'
import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'
import SummaryTOCRail from '@/components/book/SummaryTOCRail.vue'
import BackToTopFab from '@/components/book/BackToTopFab.vue'
import SummaryMetadataStrip from '@/components/book/SummaryMetadataStrip.vue'
import { firstChapter } from '@/stores/reader'
import { useUiStore } from '@/stores/ui'
import type { Section } from '@/types'

interface SectionLike {
  id: number
  order_index?: number
  section_type?: string
  has_summary?: boolean
  default_summary?: { id?: number } | null
  default_summary_id?: number | null
  summary_id?: number | null
}

interface BookLike {
  id: number
  status?: string | null
  sections?: SectionLike[]
  default_summary?: {
    summary_md?: string
    generated_at?: string
    created_at?: string
    preset_name?: string | null
    eval_passed?: number | null
    eval_total?: number | null
  } | null
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
const ui = useUiStore()

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
// FR-01..FR-07b: spinner + elapsed timer + ARIA live wiring.
const startedAt = ref<number | null>(null)
const nowTick = ref(Date.now())
let tickHandle: number | null = null

const state = computed<'populated' | 'inProgress' | 'failed' | 'empty'>(() => {
  if (props.book.default_summary && props.book.default_summary.summary_md) return 'populated'
  if (activeJobId.value !== null) return 'inProgress'
  if (props.book.last_summary_failure && !props.book.default_summary) return 'failed'
  return 'empty'
})

const elapsedMs = computed(() =>
  startedAt.value ? Math.max(0, nowTick.value - startedAt.value) : 0,
)

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  const ss = s < 10 ? `0${s}` : `${s}`
  if (m >= 10) return `${m}:${ss}`
  return `${m}:${ss}`
}

function startTimer(): void {
  if (tickHandle !== null) return
  tickHandle = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
}

function stopTimer(): void {
  if (tickHandle !== null) {
    window.clearInterval(tickHandle)
    tickHandle = null
  }
}

function attachSse(jobId: number, startedAtMs: number) {
  detachSse()
  activeJobId.value = jobId
  startedAt.value = startedAtMs
  nowTick.value = Date.now()
  startTimer()
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
  startedAt.value = null
  stopTimer()
}

onUnmounted(detachSse)

function parseStartedAt(raw: unknown): number {
  if (typeof raw === 'string') {
    const t = Date.parse(raw)
    if (!Number.isNaN(t)) return t
  }
  return Date.now()
}

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
      if (typeof jobId === 'number') attachSse(jobId, Date.now())
    } else if (r.status === 409) {
      const body = await r.json().catch(() => ({}) as Record<string, unknown>)
      const aj = (body as { active_job_id?: number }).active_job_id
      const startedRaw = (body as { active_job_started_at?: unknown })
        .active_job_started_at
      if (typeof aj === 'number') attachSse(aj, parseStartedAt(startedRaw))
    } else {
      const body = await r.json().catch(() => ({}) as Record<string, unknown>)
      errorMsg.value =
        (body as { detail?: string }).detail || `Request failed (${r.status})`
    }
  } catch (e) {
    errorMsg.value = (e as Error).message
  }
}

function readSectionSummaries() {
  const sections = (props.book.sections || []).slice()
  sections.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
  const first = firstChapter(
    sections as unknown as ReadonlyArray<Section>,
    props.book.status ?? null,
  )
  if (!first) {
    ui.showToast('No chapter to open yet', 'info')
    return
  }
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
          <TtsPlayButton
            content-type="book_summary"
            :content-id="book.id"
            :has-summary="true"
            :book-id="book.id"
          />
          <button class="btn-secondary" type="button" @click="readSectionSummaries">
            Read Section Summaries
          </button>
          <button class="btn-secondary regenerate-cta" type="button" @click="startGenerate">
            Regenerate
          </button>
        </div>
      </header>
      <SummaryMetadataStrip
        :preset="book.default_summary?.preset_name ?? null"
        :generated-at="book.default_summary?.generated_at ?? null"
        :eval-passed="book.default_summary?.eval_passed ?? null"
        :eval-total="book.default_summary?.eval_total ?? null"
      />
      <div class="book-summary-tab__layout">
        <details class="book-summary-tab__outline" open>
          <summary>Outline</summary>
          <SummaryTOCRail :content="book.default_summary!.summary_md!" />
        </details>
        <div class="book-summary-tab__body">
          <MarkdownRenderer :content="book.default_summary!.summary_md!" />
          <BackToTopFab />
        </div>
        <aside class="book-summary-tab__rail">
          <SummaryTOCRail :content="book.default_summary!.summary_md!" />
        </aside>
      </div>
    </template>

    <template v-else-if="state === 'inProgress'">
      <div
        class="book-summary-tab__progress"
        role="status"
        aria-live="polite"
        :aria-busy="true"
      >
        <div class="spinner" aria-hidden="true"></div>
        <p>Generating book summary… {{ formatElapsed(elapsedMs) }} elapsed</p>
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
.book-summary-tab__layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}
.book-summary-tab__rail {
  display: none;
}
.book-summary-tab__outline {
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
}
.book-summary-tab__outline summary {
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
}
@media (min-width: 1024px) {
  .book-summary-tab__layout {
    grid-template-columns: 1fr 16rem;
    align-items: start;
  }
  .book-summary-tab__rail {
    display: block;
  }
  .book-summary-tab__outline {
    display: none;
  }
}
.book-summary-tab__body {
  min-width: 0;
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
.spinner {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent, #4f46e5);
  animation: bc-spin 0.8s linear infinite;
}
@keyframes bc-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
  }
}
</style>
