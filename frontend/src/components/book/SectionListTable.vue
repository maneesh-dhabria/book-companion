<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES } from '@/stores/reader'
import { formatReadTime } from '@/utils/readTime'

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

// FR-C16 — collapsible group state, persisted per book in localStorage.
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

function onRowClick(s: SectionRow) {
  const query: Record<string, string> = {}
  if (props.currentSectionId !== null && route.query.tab) {
    query.tab = String(route.query.tab)
  }
  router.push({
    name: 'section-detail',
    params: { id: String(props.bookId), sectionId: String(s.id) },
    query,
  })
}

function onRowKeydown(e: KeyboardEvent, idx: number, list: SectionRow[]) {
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
    onRowClick(list[idx])
  }
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
  <table class="section-list-table" :class="{ compact }">
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th>Read time</th>
        <th>Summary</th>
      </tr>
    </thead>
    <tbody v-if="compact">
      <tr
        v-for="(s, idx) in sortedSections"
        :key="s.id"
        role="link"
        tabindex="0"
        :class="{ 'is-current': s.id === currentSectionId }"
        @click="onRowClick(s)"
        @keydown="onRowKeydown($event, idx, sortedSections)"
      >
        <td>{{ s.order_index + 1 }}</td>
        <td>{{ s.title }}</td>
        <td>{{ readTime(s) }}</td>
        <td :data-summary-kind="summaryStatus(s).kind">
          {{ summaryStatus(s).label }}
        </td>
      </tr>
    </tbody>
    <template v-else>
      <template v-for="g in groupOrder" :key="g">
        <thead v-if="groupedSections[g].length > 0" class="section-group-head">
          <tr
            class="section-group-row"
            :data-group="g"
            tabindex="0"
            role="button"
            :aria-expanded="expanded[g]"
            @click="toggleGroup(g)"
            @keydown.enter.prevent="toggleGroup(g)"
            @keydown.space.prevent="toggleGroup(g)"
          >
            <th colspan="4">
              <span class="chev" :class="{ open: expanded[g] }">▸</span>
              {{ GROUP_LABEL[g] }}
              <span class="group-count">({{ groupedSections[g].length }})</span>
            </th>
          </tr>
        </thead>
        <tbody v-if="expanded[g]" :data-group-body="g">
          <tr
            v-for="(s, idx) in groupedSections[g]"
            :key="s.id"
            role="link"
            tabindex="0"
            :class="{ 'is-current': s.id === currentSectionId }"
            @click="onRowClick(s)"
            @keydown="onRowKeydown($event, idx, groupedSections[g])"
          >
            <td>{{ s.order_index + 1 }}</td>
            <td>{{ s.title }}</td>
            <td>{{ readTime(s) }}</td>
            <td :data-summary-kind="summaryStatus(s).kind">
              {{ summaryStatus(s).label }}
            </td>
          </tr>
        </tbody>
      </template>
    </template>
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
.section-list-table thead:first-of-type th {
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
.section-group-head th {
  background: var(--color-bg-secondary, #f8fafc);
  text-transform: none;
  letter-spacing: 0;
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
}
.section-group-row:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}
.chev {
  display: inline-block;
  transition: transform 0.15s ease;
  margin-right: 0.4rem;
  color: var(--color-text-muted);
}
.chev.open {
  transform: rotate(90deg);
}
.group-count {
  margin-left: 0.4rem;
  color: var(--color-text-muted);
  font-weight: 400;
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
</style>
