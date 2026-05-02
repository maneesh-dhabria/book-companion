<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { formatCompression } from './SectionListTable.formatters'

interface SectionRow {
  id: number
  title: string
  order_index: number
  section_type: string
  content_char_count?: number | null
  has_summary: boolean
  default_summary?: { summary_char_count: number } | null
  last_failure_type?: string | null
}

const props = withDefaults(
  defineProps<{
    sections: SectionRow[]
    bookId: number
    compact?: boolean
    currentSectionId?: number | null
  }>(),
  { compact: false, currentSectionId: null },
)

const router = useRouter()
const route = useRoute()
const jobStore = useSummarizationJobStore()

type LiveStatus = 'pending' | 'completed' | 'failed' | 'retrying'
const liveStatuses = ref<Record<number, LiveStatus>>({})

const sortedSections = computed(() =>
  [...props.sections].sort((a, b) => a.order_index - b.order_index),
)

function compressionLabel(s: SectionRow): string {
  if (!s.has_summary || !s.default_summary || !s.content_char_count) return '—'
  if (s.content_char_count === 0) return '—'
  const pct = (s.default_summary.summary_char_count / s.content_char_count) * 100
  return formatCompression(pct)
}

interface SummaryStatus {
  label: string
  kind: 'done' | 'pending' | 'failed' | 'none'
}

function summaryStatus(s: SectionRow): SummaryStatus {
  const live = liveStatuses.value[s.id]
  if (live === 'completed') return { label: '✓', kind: 'done' }
  if (live === 'failed') return { label: 'failed', kind: 'failed' }
  if (live === 'retrying') return { label: 'retrying…', kind: 'pending' }
  if (live === 'pending') return { label: 'pending', kind: 'pending' }
  if (s.has_summary) return { label: '✓', kind: 'done' }
  if (s.last_failure_type) return { label: 'failed', kind: 'failed' }
  return { label: '—', kind: 'none' }
}

function onRowClick(s: SectionRow) {
  const query: Record<string, string> = {}
  // Only propagate ?tab when we're called from the reader-TOC context
  // (currentSectionId provided). Book-detail callers leave it untouched.
  if (props.currentSectionId !== null && route.query.tab) {
    query.tab = String(route.query.tab)
  }
  router.push({
    name: 'section-detail',
    params: { id: String(props.bookId), sectionId: String(s.id) },
    query,
  })
}

function onRowKeydown(e: KeyboardEvent, idx: number) {
  const target = e.currentTarget as HTMLElement
  const tbody = target.parentElement
  if (!tbody) return
  const rows = tbody.querySelectorAll<HTMLElement>('tr[role="link"]')
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    rows[idx + 1]?.focus()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    rows[idx - 1]?.focus()
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    onRowClick(sortedSections.value[idx])
  }
}

function showSeparatorBefore(idx: number): boolean {
  if (idx === 0) return false
  return (
    sortedSections.value[idx].section_type !==
    sortedSections.value[idx - 1].section_type
  )
}

// FR-33a — react to SSE updates from the existing summarization-job store.
// Compact mode is read-only (Decision Log P8): the reader-TOC dropdown
// already has its own job-aware surface, and we want to keep the
// dropdown render lightweight when the user is mid-tap.
if (!props.compact) {
  watch(
    () => jobStore.lastEvent,
    (ev) => {
      if (!ev) return
      const sid = ev.data?.section_id
      if (ev.event === 'processing_completed' || ev.event === 'processing_failed') {
        liveStatuses.value = {}
        return
      }
      if (typeof sid !== 'number') return
      if (!props.sections.some((s) => s.id === sid)) return
      switch (ev.event) {
        case 'section_started':
          liveStatuses.value = { ...liveStatuses.value, [sid]: 'pending' }
          break
        case 'section_completed':
          liveStatuses.value = { ...liveStatuses.value, [sid]: 'completed' }
          break
        case 'section_failed':
          liveStatuses.value = { ...liveStatuses.value, [sid]: 'failed' }
          break
        case 'section_retry':
          liveStatuses.value = { ...liveStatuses.value, [sid]: 'retrying' }
          break
      }
    },
  )
}
</script>

<template>
  <table class="section-list-table" :class="{ compact }">
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th v-if="!compact">Type</th>
        <th>Chars</th>
        <th>Summary</th>
        <th v-if="!compact">Compression</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="(s, idx) in sortedSections" :key="s.id">
        <tr
          v-if="showSeparatorBefore(idx)"
          class="section-type-separator"
          aria-hidden="true"
        >
          <td :colspan="compact ? 4 : 6"></td>
        </tr>
        <tr
          role="link"
          tabindex="0"
          :class="{ 'is-current': s.id === currentSectionId }"
          @click="onRowClick(s)"
          @keydown="onRowKeydown($event, idx)"
        >
          <td>{{ s.order_index + 1 }}</td>
          <td>{{ s.title }}</td>
          <td v-if="!compact">{{ s.section_type }}</td>
          <td>{{ (s.content_char_count ?? 0).toLocaleString() }}</td>
          <td :data-summary-kind="summaryStatus(s).kind">{{ summaryStatus(s).label }}</td>
          <td v-if="!compact">{{ compressionLabel(s) }}</td>
        </tr>
      </template>
    </tbody>
  </table>
</template>

<style scoped>
.section-list-table {
  width: 100%;
  border-collapse: collapse;
}
.section-list-table th,
.section-list-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  font-size: 14px;
}
.section-list-table th {
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.section-list-table tr[role='link'] {
  cursor: pointer;
}
.section-list-table tr[role='link']:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}
.section-list-table tr[role='link']:hover {
  background: var(--color-bg-tertiary);
}
.section-list-table tr.is-current {
  background: rgba(79, 70, 229, 0.08);
}
.section-list-table tr.section-type-separator {
  height: 1px;
}
.section-list-table tr.section-type-separator td {
  padding: 0;
  border-bottom: 1px solid var(--color-border-strong);
}
.section-list-table.compact th,
.section-list-table.compact td {
  padding: 4px 8px;
  font-size: 13px;
}
.section-list-table.compact {
  max-width: 360px;
}
[data-summary-kind='done'] {
  color: var(--color-success);
  font-weight: 600;
}
[data-summary-kind='failed'] {
  color: var(--color-error);
  font-weight: 600;
}
[data-summary-kind='pending'] {
  color: var(--color-warning);
}
[data-summary-kind='none'] {
  color: var(--color-text-muted);
}
@media (max-width: 640px) {
  .section-list-table:not(.compact) th:nth-child(3),
  .section-list-table:not(.compact) td:nth-child(3),
  .section-list-table:not(.compact) th:nth-child(6),
  .section-list-table:not(.compact) td:nth-child(6) {
    display: none;
  }
}
</style>
