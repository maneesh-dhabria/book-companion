<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES } from '@/stores/reader'
import { formatReadTime } from '@/utils/readTime'
import { useBookAudioMap } from '@/composables/useBookAudioMap'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

interface SectionRow {
  id: number
  title: string
  order_index: number
  section_type: string
  content_char_count?: number | null
  has_summary: boolean
  default_summary?: { summary_char_count: number; id?: number } | null
  default_summary_id?: number | null
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

const emit = defineEmits<{
  'more-actions': [sectionId: number]
}>()

const router = useRouter()
const route = useRoute()
const jobStore = useSummarizationJobStore()
const ttsPlayer = useTtsPlayerStore()

// FR-C20 — batch audio-availability map. Used by both modes:
// non-compact for the row Listen affordance (T19); compact for the
// 🎧 chip in TOCDropdown rows (T21, FR-D04). Cache dedups the fetch.
const audio = useBookAudioMap(props.bookId)

type LiveStatus = 'pending' | 'completed' | 'failed' | 'retrying'
const liveStatuses = ref<Record<number, LiveStatus>>({})

type GroupKey = 'front' | 'chapters' | 'back'
const GROUP_LABEL: Record<GroupKey, string> = {
  front: 'Front matter',
  chapters: 'Chapters',
  back: 'Back matter',
}

function groupOf(sectionType: string): GroupKey {
  if (FRONT_MATTER_TYPES.has(sectionType)) return 'front'
  if (SUMMARIZABLE_TYPES.has(sectionType)) return 'chapters'
  return 'back'
}

const sortedSections = computed(() =>
  [...props.sections].sort((a, b) => a.order_index - b.order_index),
)

const groupedSections = computed<Record<GroupKey, SectionRow[]>>(() => {
  const out: Record<GroupKey, SectionRow[]> = { front: [], chapters: [], back: [] }
  for (const s of sortedSections.value) out[groupOf(s.section_type)].push(s)
  return out
})

const groupOrder: GroupKey[] = ['front', 'chapters', 'back']

const expandKey = computed(() => `bc.sections.expand.${props.bookId}`)

function loadExpanded(): Record<GroupKey, boolean> {
  const fallback: Record<GroupKey, boolean> = { front: false, chapters: true, back: false }
  if (typeof localStorage === 'undefined') return fallback
  try {
    const raw = localStorage.getItem(expandKey.value)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<Record<GroupKey, boolean>>
    return {
      front: parsed.front ?? false,
      chapters: parsed.chapters ?? true,
      back: parsed.back ?? false,
    }
  } catch {
    return fallback
  }
}

const expanded = ref<Record<GroupKey, boolean>>(loadExpanded())

function toggleGroup(g: GroupKey) {
  expanded.value = { ...expanded.value, [g]: !expanded.value[g] }
  try {
    if (typeof localStorage !== 'undefined')
      localStorage.setItem(expandKey.value, JSON.stringify(expanded.value))
  } catch {
    // best-effort persistence
  }
}

watch(
  () => props.bookId,
  () => {
    expanded.value = loadExpanded()
  },
)

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
  return { label: '✕', kind: 'none' }
}

function readTime(s: SectionRow): string {
  return formatReadTime(s.content_char_count ?? 0)
}

function summaryRoute(s: SectionRow) {
  return {
    name: 'section-detail' as const,
    params: { id: String(props.bookId), sectionId: String(s.id) },
    query: { tab: 'summary' },
  }
}

function readRoute(s: SectionRow) {
  return {
    name: 'section-detail' as const,
    params: { id: String(props.bookId), sectionId: String(s.id) },
  }
}

function onRowClick(e: MouseEvent, s: SectionRow) {
  // Cmd/Ctrl-click → open in new tab (FR-C17a).
  if (e.metaKey || e.ctrlKey) {
    const href = router.resolve(summaryRoute(s)).href
    window.open(href, '_blank', 'noopener,noreferrer')
    return
  }
  navigateRow(s)
}

function onRowAuxClick(e: MouseEvent, s: SectionRow) {
  // Middle-click also opens in new tab.
  if (e.button === 1) {
    e.preventDefault()
    const href = router.resolve(summaryRoute(s)).href
    window.open(href, '_blank', 'noopener,noreferrer')
  }
}

function navigateRow(s: SectionRow) {
  // Reader-TOC context (currentSectionId set) preserves the existing
  // ?tab query so the user stays in the same tab they were reading.
  // Book-overview context navigates to ?tab=summary by default.
  if (props.currentSectionId !== null) {
    const query: Record<string, string> = {}
    if (route.query.tab) query.tab = String(route.query.tab)
    router.push({
      name: 'section-detail',
      params: { id: String(props.bookId), sectionId: String(s.id) },
      query,
    })
  } else {
    router.push(summaryRoute(s))
  }
}

function onRowKeydown(e: KeyboardEvent, idx: number, list: SectionRow[]) {
  const target = e.currentTarget as HTMLElement
  const container = target.parentElement
  if (!container) return
  const rows = container.querySelectorAll<HTMLElement>('[role="link"], [role="button"][data-row]')
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    rows[idx + 1]?.focus()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    rows[idx - 1]?.focus()
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    navigateRow(list[idx])
  }
}

function canListen(s: SectionRow): boolean {
  // FR-C20 — Listen disabled iff no MP3 AND no summary. When the audio
  // batch lookup failed (e.g. backend down), allow Listen for everything
  // (degraded fallback).
  if (audio.failed.value) return true
  const hasMp3 = audio.map.value[s.id]?.has_mp3 ?? false
  return hasMp3 || s.has_summary || !!s.default_summary_id
}

function hasMp3(s: SectionRow): boolean {
  return audio.map.value[s.id]?.has_mp3 ?? false
}

function onListen(s: SectionRow) {
  // Wire to the existing TTS player store so the section's summary plays.
  ttsPlayer.open({
    bookId: props.bookId,
    contentType: 'section_summary',
    contentId: s.id,
  })
}

function onRead(s: SectionRow) {
  router.push(readRoute(s))
}

function onMore(s: SectionRow) {
  emit('more-actions', s.id)
}

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
  <!-- Compact mode (reader-TOC dropdown): keep the dense table layout. -->
  <table v-if="compact" class="section-list-table compact">
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th>Read time</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(s, idx) in sortedSections"
        :key="s.id"
        role="link"
        tabindex="0"
        :class="{ 'is-current': s.id === currentSectionId }"
        @click="navigateRow(s)"
        @keydown="onRowKeydown($event, idx, sortedSections)"
      >
        <td>{{ s.order_index + 1 }}</td>
        <td>{{ s.title }}</td>
        <td>{{ readTime(s) }}</td>
        <td class="compact-chips">
          <span
            class="chip chip--neutral"
            data-chip="mode"
            :title="s.has_summary ? 'Summary available' : 'Original only'"
          >{{ s.has_summary ? '📋' : '📖' }}</span>
          <span
            class="chip"
            :class="summaryStatus(s).kind === 'done' ? 'chip--accent' : 'chip--neutral'"
            data-chip="summary"
            :data-summary-kind="summaryStatus(s).kind"
            :title="summaryStatus(s).kind === 'done' ? 'Summarized' : 'Not summarized'"
          >{{ summaryStatus(s).label }}</span>
          <span
            v-if="hasMp3(s)"
            class="chip chip--info"
            data-chip="audio"
            title="Audio available"
          >🎧</span>
        </td>
      </tr>
    </tbody>
  </table>

  <!-- Default (book-overview Sections tab): div-grid stack, hover actions. -->
  <div v-else class="section-list" role="table" aria-label="Sections">
    <div class="section-list-header" role="row">
      <span class="col-index">#</span>
      <span class="col-title">Title</span>
      <span class="col-time">Read time</span>
      <span class="col-summary">Summary</span>
    </div>
    <template v-for="g in groupOrder" :key="g">
      <div
        v-if="groupedSections[g].length > 0"
        class="section-group-row"
        :data-group="g"
        role="button"
        tabindex="0"
        :aria-expanded="expanded[g]"
        @click="toggleGroup(g)"
        @keydown.enter.prevent="toggleGroup(g)"
        @keydown.space.prevent="toggleGroup(g)"
      >
        <span class="chev" :class="{ open: expanded[g] }">▸</span>
        {{ GROUP_LABEL[g] }}
        <span class="group-count">({{ groupedSections[g].length }})</span>
      </div>
      <div v-if="expanded[g]" :data-group-body="g">
        <div
          v-for="(s, idx) in groupedSections[g]"
          :key="s.id"
          class="section-row group"
          data-row
          role="button"
          tabindex="0"
          :aria-label="`Open summary of ${s.title}`"
          :class="{ 'is-current': s.id === currentSectionId }"
          @click="onRowClick($event, s)"
          @auxclick="onRowAuxClick($event, s)"
          @keydown="onRowKeydown($event, idx, groupedSections[g])"
        >
          <span class="col-index">{{ s.order_index + 1 }}</span>
          <span class="col-title">{{ s.title }}</span>
          <span class="col-time">{{ readTime(s) }}</span>
          <span class="col-summary" :data-summary-kind="summaryStatus(s).kind">
            {{ summaryStatus(s).label }}
          </span>
          <div class="row-actions">
            <button
              type="button"
              class="row-action"
              data-action="listen"
              :disabled="!canListen(s)"
              :title="canListen(s) ? 'Listen' : 'Generate a summary or audio first'"
              @click.stop="onListen(s)"
              @auxclick.stop
            >
              ▶
            </button>
            <button
              type="button"
              class="row-action"
              data-action="read"
              title="Read original"
              @click.stop="onRead(s)"
              @auxclick.stop
            >
              📖
            </button>
            <button
              type="button"
              class="row-action"
              data-action="more"
              title="More"
              @click.stop="onMore(s)"
              @auxclick.stop
            >
              ⋯
            </button>
          </div>
          <span class="row-chev" aria-hidden="true">›</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Compact (reader-TOC dropdown) — table layout preserved. */
.section-list-table.compact {
  width: 100%;
  border-collapse: collapse;
  max-width: 360px;
}
.section-list-table.compact th,
.section-list-table.compact td {
  text-align: left;
  padding: 4px 8px;
  font-size: 13px;
  border-bottom: 1px solid var(--color-border);
}
.section-list-table.compact th {
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.section-list-table.compact tr[role='link'] {
  cursor: pointer;
}
.section-list-table.compact tr[role='link']:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}
.section-list-table.compact tr[role='link']:hover {
  background: var(--color-bg-tertiary);
}
.section-list-table.compact tr.is-current {
  background: rgba(79, 70, 229, 0.08);
}

/* Default (book-overview Sections tab) — div-grid stack. */
.section-list {
  display: flex;
  flex-direction: column;
}
.section-list-header,
.section-row {
  display: grid;
  grid-template-columns: 3rem 1fr 6rem 4rem auto 1.5rem;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
  font-size: 0.9rem;
}
.section-list-header {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600;
  color: var(--color-text-secondary, #475569);
  border-bottom: 1px solid var(--color-border-strong, #cbd5e1);
}
.section-row {
  cursor: pointer;
  position: relative;
}
.section-row:hover {
  background: var(--color-bg-secondary, #f8fafc);
}
.section-row:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: -2px;
}
.section-row.is-current {
  background: rgba(79, 70, 229, 0.08);
}
.col-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-time,
.col-summary {
  font-size: 0.85rem;
}
.row-actions {
  display: flex;
  gap: 0.25rem;
  opacity: 0;
  transition: opacity 0.1s ease;
}
.section-row:hover .row-actions,
.section-row:focus-within .row-actions {
  opacity: 1;
}
.row-action {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0.2rem 0.4rem;
  border-radius: 0.25rem;
  color: var(--color-text-secondary, #475569);
}
.row-action:hover:not(:disabled) {
  background: var(--color-bg-tertiary, #e2e8f0);
}
.row-action:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.row-action:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: 1px;
}
.row-chev {
  color: var(--color-text-muted, #94a3b8);
  font-size: 1.1rem;
}

.section-group-row {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: var(--color-bg-secondary, #f8fafc);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-primary, #1f2937);
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}
.section-group-row:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: -2px;
}
.chev {
  display: inline-block;
  transition: transform 0.15s ease;
  margin-right: 0.4rem;
  color: var(--color-text-muted, #94a3b8);
}
.chev.open {
  transform: rotate(90deg);
}
.group-count {
  margin-left: 0.4rem;
  color: var(--color-text-muted, #94a3b8);
  font-weight: 400;
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
</style>
