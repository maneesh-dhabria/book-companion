<script setup lang="ts">
import { useSearchStore } from '@/stores/search'
import { useUiStore } from '@/stores/ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const searchStore = useSearchStore()
const uiStore = useUiStore()
const router = useRouter()
const inputRef = ref<HTMLInputElement | null>(null)
const debouncing = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  inputRef.value?.focus()
  searchStore.loadRecentSearches()
})

function handleInput(e: Event) {
  const q = (e.target as HTMLInputElement).value
  if (debounceTimer) clearTimeout(debounceTimer)
  debouncing.value = !!q.trim()
  debounceTimer = setTimeout(async () => {
    await searchStore.doQuickSearch(q)
    debouncing.value = false
  }, 200)
}

const isLoading = computed(() => debouncing.value || searchStore.quickLoading)
const totalHits = computed(() => {
  const r = searchStore.quickResults
  if (!r) return 0
  return (
    (r.sections?.length || 0) +
    (r.concepts?.length || 0) +
    (r.annotations?.length || 0)
  )
})
const showNoResults = computed(() =>
  !isLoading.value &&
  searchStore.query.trim() !== '' &&
  searchStore.quickResults !== null &&
  totalHits.value === 0,
)

function navigateToResult(type: string, id: number, bookId?: number) {
  uiStore.closePalette()
  if (type === 'section' && bookId) {
    router.push(`/books/${bookId}/sections/${id}`)
  } else if (type === 'book') {
    router.push(`/books/${id}`)
  } else if (type === 'concept') {
    router.push(`/concepts?id=${id}`)
  } else if (type === 'annotation') {
    router.push(`/annotations?id=${id}`)
  }
}

function openFullSearch() {
  uiStore.closePalette()
  router.push(`/search?q=${encodeURIComponent(searchStore.query)}`)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="uiStore.commandPaletteOpen" class="palette-overlay" @click.self="uiStore.closePalette()">
      <div class="palette-modal">
        <div class="palette-search">
          <input
            ref="inputRef"
            type="text"
            :value="searchStore.query"
            @input="handleInput"
            @keydown.escape="uiStore.closePalette()"
            @keydown.enter="openFullSearch"
            placeholder="Search books, sections, concepts..."
            class="palette-input"
          />
        </div>

        <div
          v-if="isLoading"
          class="palette-loading"
          data-testid="palette-loading"
        >
          <span class="spinner" aria-hidden="true" />
          Searching…
        </div>

        <div
          v-else-if="showNoResults"
          class="palette-empty"
          data-testid="palette-no-results"
        >
          <p>No results for "{{ searchStore.query }}"</p>
          <button class="full-search-btn" @click="openFullSearch">
            Try full search →
          </button>
        </div>

        <div class="palette-results" v-else-if="searchStore.quickResults">
          <template v-if="searchStore.quickResults.sections.length">
            <h4 class="group-title">Sections</h4>
            <button
              v-for="hit in searchStore.quickResults.sections"
              :key="'s' + hit.id"
              class="result-item"
              @click="navigateToResult('section', hit.id, hit.book_id)"
            >
              <span class="result-title">{{ hit.title }}</span>
              <span class="result-meta">{{ hit.book_title }}</span>
            </button>
          </template>

          <template v-if="searchStore.quickResults.concepts.length">
            <h4 class="group-title">Concepts</h4>
            <button
              v-for="hit in searchStore.quickResults.concepts"
              :key="'c' + hit.id"
              class="result-item"
              @click="navigateToResult('concept', hit.id)"
            >
              <span class="result-title">{{ hit.term }}</span>
              <span class="result-snippet">{{ hit.snippet }}</span>
            </button>
          </template>

          <template v-if="searchStore.quickResults.annotations.length">
            <h4 class="group-title">Annotations</h4>
            <button
              v-for="hit in searchStore.quickResults.annotations"
              :key="'a' + hit.id"
              class="result-item"
              @click="navigateToResult('annotation', hit.id)"
            >
              <span class="result-title">{{ hit.note_snippet || hit.selected_text || 'Annotation' }}</span>
              <span class="result-meta">{{ hit.book_title }}</span>
            </button>
          </template>

          <div v-if="searchStore.query" class="palette-footer">
            <button class="full-search-btn" @click="openFullSearch">
              View all results for "{{ searchStore.query }}" →
            </button>
          </div>
        </div>

        <div v-else-if="searchStore.recentSearches.length" class="recent-searches">
          <h4 class="group-title">Recent Searches</h4>
          <button
            v-for="recent in searchStore.recentSearches"
            :key="recent.id"
            class="result-item"
            @click="searchStore.doQuickSearch(recent.query)"
          >
            <span class="result-title">{{ recent.query }}</span>
            <span class="result-meta" v-if="recent.result_count !== null">{{ recent.result_count }} results</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.palette-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; justify-content: center; padding-top: 15vh; }
.palette-modal { width: 560px; max-height: 60vh; background: var(--color-bg, #fff); border-radius: 0.75rem; box-shadow: 0 16px 48px rgba(0,0,0,0.2); overflow: hidden; display: flex; flex-direction: column; }
.palette-search { padding: 0.75rem; border-bottom: 1px solid var(--color-border, #e0e0e0); }
.palette-input { width: 100%; border: none; outline: none; font-size: 1rem; padding: 0.25rem; background: transparent; }
.palette-results, .recent-searches { overflow-y: auto; padding: 0.5rem; }
.group-title { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary, #888); padding: 0.375rem 0.5rem; margin: 0; }
.result-item { width: 100%; display: flex; flex-direction: column; gap: 0.125rem; padding: 0.5rem 0.75rem; border: none; background: transparent; cursor: pointer; border-radius: 0.375rem; text-align: left; }
.result-item:hover { background: var(--color-bg-hover, #f3f4f6); }
.result-title { font-size: 0.85rem; font-weight: 500; }
.result-meta { font-size: 0.7rem; color: var(--color-text-secondary, #888); }
.result-snippet { font-size: 0.75rem; color: var(--color-text-secondary, #666); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.palette-footer { padding: 0.5rem; border-top: 1px solid var(--color-border, #e0e0e0); }
.full-search-btn { width: 100%; padding: 0.5rem; background: none; border: none; cursor: pointer; color: var(--color-primary, #3b82f6); font-size: 0.85rem; text-align: center; border-radius: 0.375rem; }
.full-search-btn:hover { background: var(--color-bg-hover, #f3f4f6); }
.palette-loading, .palette-empty {
  padding: 1.25rem 1rem;
  color: var(--color-text-secondary, #888);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.palette-loading { flex-direction: row; justify-content: center; }
.palette-loading .spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border, #ddd);
  border-top-color: var(--color-primary, #3b82f6);
  border-radius: 50%;
  animation: cpspin 0.8s linear infinite;
}
@keyframes cpspin { to { transform: rotate(360deg); } }
</style>
