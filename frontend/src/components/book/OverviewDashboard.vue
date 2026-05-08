<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Section } from '@/types'
import { firstChapter } from '@/stores/reader'
import { formatReadTimeSum } from '@/utils/readTime'
import { formatDate } from '@/utils/formatDate'

interface BookInput {
  id: number
  status?: string | null
  default_summary?:
    | { summary_md?: string; generated_at?: string | null; preset?: string | null }
    | null
  sections?: Section[]
}

interface ConceptItem {
  id: number
  term: string
  book_id: number
  created_at: string
}

const props = defineProps<{ book: BookInput }>()

const concepts = ref<ConceptItem[] | null>(null)
const lastSectionId = ref<number | null>(null)
const lastSectionTitle = ref<string | null>(null)
const readerStateLoaded = ref(false)

async function loadConcepts(bookId: number) {
  try {
    const r = await fetch(`/api/v1/concepts?book_id=${bookId}&per_page=200`)
    if (!r.ok) {
      concepts.value = []
      return
    }
    const data = await r.json()
    const items = (data.items ?? []) as ConceptItem[]
    items.sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0))
    concepts.value = items.slice(0, 5)
  } catch {
    concepts.value = []
  }
}

async function loadReaderState(bookId: number) {
  try {
    const r = await fetch(`/api/v1/reading-state/by-book/${bookId}`)
    if (!r.ok) {
      readerStateLoaded.value = true
      return
    }
    const data = await r.json()
    lastSectionId.value = data.last_section_id ?? null
    lastSectionTitle.value = data.section_title ?? null
  } catch {
    // best-effort
  } finally {
    readerStateLoaded.value = true
  }
}

onMounted(() => {
  loadConcepts(props.book.id)
  loadReaderState(props.book.id)
})

watch(
  () => props.book.id,
  (id) => {
    concepts.value = null
    readerStateLoaded.value = false
    loadConcepts(id)
    loadReaderState(id)
  },
)

const targetSection = computed<Section | null>(() =>
  firstChapter(props.book.sections ?? null, props.book.status ?? null),
)

const continueTitle = computed(() =>
  lastSectionId.value != null ? 'Continue reading' : 'Start reading',
)

const continueSubtitle = computed(() => {
  const t = targetSection.value
  if (!t) return 'Waiting for the first chapter to parse.'
  return `§${t.order_index} · ${t.title}`
})

const continueRoute = computed(() => {
  const t = targetSection.value
  if (!t) return null
  return `/books/${props.book.id}/sections/${t.id}`
})

const summaryGeneratedAt = computed(() => props.book.default_summary?.generated_at ?? null)
const summaryPreset = computed(() => props.book.default_summary?.preset ?? null)
const hasBookSummary = computed(() => !!props.book.default_summary?.summary_md)

const summarySubtitle = computed(() => {
  if (!hasBookSummary.value) return 'No book summary — Generate'
  const rel = summaryGeneratedAt.value ? formatDate(summaryGeneratedAt.value) : ''
  const presetLabel = summaryPreset.value ? `${summaryPreset.value} · ` : ''
  return `Available · ${presetLabel}last generated ${rel}`
})

const summaryRoute = computed(() => `/books/${props.book.id}?tab=summary`)

const sectionsCount = computed(() => (props.book.sections ?? []).length)
const sectionsReadTime = computed(() =>
  formatReadTimeSum((props.book.sections ?? []).map((s) => s.content_char_count ?? 0)),
)
const sectionsRoute = computed(() => `/books/${props.book.id}?tab=sections`)

function conceptRoute(term: string) {
  return `/concepts?book=${props.book.id}&concept=${encodeURIComponent(term)}`
}
</script>

<template>
  <div class="overview-dashboard">
    <router-link
      v-if="continueRoute"
      :to="continueRoute"
      class="tile"
      data-testid="tile-continue"
    >
      <div class="tile-title">{{ continueTitle }}</div>
      <div class="tile-subtitle">{{ continueSubtitle }}</div>
    </router-link>
    <div v-else class="tile tile--disabled" data-testid="tile-continue">
      <div class="tile-title">{{ continueTitle }}</div>
      <div class="tile-subtitle">{{ continueSubtitle }}</div>
    </div>

    <router-link :to="summaryRoute" class="tile" data-testid="tile-summary">
      <div class="tile-title">Book summary</div>
      <div class="tile-subtitle">{{ summarySubtitle }}</div>
    </router-link>

    <div class="tile" data-testid="tile-concepts">
      <div class="tile-title">Top concepts</div>
      <template v-if="concepts === null">
        <div class="skeleton skeleton-line skeleton-w-80"></div>
        <div class="skeleton skeleton-line skeleton-w-60"></div>
        <div class="skeleton skeleton-line skeleton-w-70"></div>
      </template>
      <template v-else-if="concepts.length === 0">
        <div class="tile-subtitle">No concepts mined yet</div>
      </template>
      <template v-else>
        <div class="concept-chips">
          <router-link
            v-for="c in concepts"
            :key="c.id"
            :to="conceptRoute(c.term)"
            class="chip chip--accent"
          >
            {{ c.term }}
          </router-link>
        </div>
      </template>
    </div>

    <router-link :to="sectionsRoute" class="tile" data-testid="tile-sections">
      <div class="tile-title">Sections</div>
      <div class="tile-subtitle">
        {{ sectionsCount }} sections · ≈ {{ sectionsReadTime }} read · See all
      </div>
    </router-link>
  </div>
</template>

<style scoped>
.overview-dashboard {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 768px) {
  .overview-dashboard {
    grid-template-columns: 1fr 1fr;
  }
}

.tile {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 0.5rem;
  background: var(--color-bg-primary, #fff);
  text-decoration: none;
  color: var(--color-text-primary, #111);
  transition: background 0.1s, border-color 0.1s;
}

.tile:hover {
  background: var(--color-bg-secondary, #f8fafc);
  border-color: var(--color-border-strong, #cbd5e1);
}

.tile:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: 2px;
}

.tile--disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tile-title {
  font-weight: 600;
  font-size: 0.95rem;
}

.tile-subtitle {
  font-size: 0.85rem;
  color: var(--color-text-secondary, #475569);
}

.concept-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.skeleton {
  background: var(--color-bg-muted, #e2e8f0);
  border-radius: 0.25rem;
  animation: pulse 1.4s ease-in-out infinite;
}

.skeleton-line {
  height: 0.85rem;
}

.skeleton-w-60 {
  width: 60%;
}
.skeleton-w-70 {
  width: 70%;
}
.skeleton-w-80 {
  width: 80%;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}
</style>
