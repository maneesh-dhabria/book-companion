<template>
  <div data-test="scope-picker" class="scope-picker">
    <fieldset class="scope-mode">
      <legend>Quiz scope</legend>
      <label>
        <input
          type="radio"
          name="scope-mode"
          value="all_summaries"
          data-test="scope-mode-all"
          :checked="scopeMode === 'all_summaries'"
          @change="setScopeMode('all_summaries')"
        />
        All summaries
      </label>
      <label>
        <input
          type="radio"
          name="scope-mode"
          value="specific_chapters"
          data-test="scope-mode-specific"
          :checked="scopeMode === 'specific_chapters'"
          @change="setScopeMode('specific_chapters')"
        />
        Specific chapters
      </label>
    </fieldset>

    <template v-if="scopeMode === 'specific_chapters'">
      <ChapterMultiSelect
        :sections="sections"
        :selected-ids="selectedSectionIds"
        :budget-used="usedTokens"
        :budget-max="budgetMax"
        @toggle="toggleSection"
      />
      <BudgetBar
        :used-tokens="usedTokens"
        :max-tokens="budgetMax"
        :attempted-overflow="attemptedOverflow"
      />
      <p
        v-if="attemptedOverflow"
        data-test="overflow-msg"
        class="helper-text helper-text-error"
      >
        {{ COPY.wouldExceedBudget }}
      </p>
      <p
        v-else-if="selectedSectionIds.length === 0"
        data-test="empty-selection-msg"
        class="helper-text helper-text-warn"
      >
        {{ COPY.pickAtLeastOneChapter }}
      </p>
    </template>

    <ThemeInput v-model="theme" />

    <div class="actions">
      <button
        type="button"
        class="btn-primary"
        data-test="start"
        :disabled="!canStart"
        @click="onStart"
      >
        Start quiz
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BudgetBar from './BudgetBar.vue'
import ChapterMultiSelect from './ChapterMultiSelect.vue'
import ThemeInput from './ThemeInput.vue'
import { COPY } from './copy'
import { getReadingStateByBook } from '@/api/readingState'
import type { QuizScopeMode, SectionBrief } from '@/types'

const props = defineProps<{
  bookId: number
  sections: SectionBrief[]
  budgetMax?: number
  /** Optional seed for the theme input (FR-63). When this changes the local theme is overwritten. */
  seededTheme?: string | null
}>()

const emit = defineEmits<{
  start: [{ scope: { mode: QuizScopeMode; section_ids: number[] | null }; theme: string | null }]
  change: []
}>()

const budgetMax = computed(() => props.budgetMax ?? 60_000)

const scopeMode = ref<QuizScopeMode>('all_summaries')
const selectedSectionIds = ref<number[]>([])
const theme = ref<string | null>(null)
const attemptedOverflow = ref(false)

// FR-63: chip clicks in ThemesCoveredPanel arrive here via the parent.
watch(
  () => props.seededTheme,
  (next) => {
    if (next != null && next.length > 0) theme.value = next
  },
)

// FR-05: any input mutation clears the inline diagnostic upstream so the
// hero stays in sync with the user's current intent.
watch([scopeMode, selectedSectionIds, theme], () => emit('change'), { deep: true })

const ELIGIBLE_TYPES = new Set(['chapter', 'part', 'section'])
const lsKey = computed(() => `quiz.lastScope.book-${props.bookId}`)

function tokensFor(s: SectionBrief): number {
  return s.content_token_count ?? Math.ceil((s.content_char_count ?? 0) / 4)
}

const usedTokens = computed(() => {
  const ids = new Set(selectedSectionIds.value)
  return props.sections.filter((s) => ids.has(s.id)).reduce((sum, s) => sum + tokensFor(s), 0)
})

const canStart = computed(() => {
  if (scopeMode.value === 'all_summaries') return true
  return selectedSectionIds.value.length > 0 && usedTokens.value <= budgetMax.value
})

function setScopeMode(m: QuizScopeMode) {
  scopeMode.value = m
  attemptedOverflow.value = false
}

function toggleSection(id: number) {
  attemptedOverflow.value = false
  if (selectedSectionIds.value.includes(id)) {
    selectedSectionIds.value = selectedSectionIds.value.filter((x) => x !== id)
    return
  }
  // Adding — check budget
  const sec = props.sections.find((s) => s.id === id)
  if (!sec) return
  const projected = usedTokens.value + tokensFor(sec)
  if (projected > budgetMax.value) {
    attemptedOverflow.value = true
    return
  }
  selectedSectionIds.value = [...selectedSectionIds.value, id]
}

async function applyDefaultScope() {
  // D31 priority: 1) recently-read sections (T14 endpoint), 2) localStorage last
  // scope, 3) fallback to all_summaries.
  try {
    const rs = await getReadingStateByBook(props.bookId)
    const recent = rs.most_recent_section_ids.filter((id) =>
      props.sections.some((s) => s.id === id && ELIGIBLE_TYPES.has(s.section_type)),
    )
    if (recent.length > 0) {
      scopeMode.value = 'specific_chapters'
      selectedSectionIds.value = recent
      return
    }
  } catch {
    // ignore — fall through
  }
  const cached = localStorage.getItem(lsKey.value)
  if (cached) {
    try {
      const parsed = JSON.parse(cached) as {
        mode: QuizScopeMode
        section_ids?: number[]
      }
      scopeMode.value = parsed.mode
      if (parsed.mode === 'specific_chapters' && parsed.section_ids) {
        selectedSectionIds.value = parsed.section_ids.filter((id) =>
          props.sections.some((s) => s.id === id),
        )
      }
      return
    } catch {
      /* fall through */
    }
  }
  scopeMode.value = 'all_summaries'
}

onMounted(applyDefaultScope)

// Persist last-used scope on every change so future visits can replay.
watch([scopeMode, selectedSectionIds], () => {
  try {
    localStorage.setItem(
      lsKey.value,
      JSON.stringify({
        mode: scopeMode.value,
        section_ids: selectedSectionIds.value,
      }),
    )
  } catch {
    /* SSR / quota — ignore */
  }
})

function onStart() {
  if (!canStart.value) return
  emit('start', {
    scope: {
      mode: scopeMode.value,
      section_ids: scopeMode.value === 'specific_chapters' ? [...selectedSectionIds.value] : null,
    },
    theme: theme.value,
  })
}

defineExpose({ scopeMode, selectedSectionIds })
</script>

<style scoped>
.scope-picker {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-border, #e5e5e5);
  border-radius: 6px;
}
.scope-mode {
  border: none;
  display: flex;
  gap: 1rem;
  padding: 0;
}
.scope-mode legend {
  font-weight: 600;
  margin-bottom: 0.25rem;
}
.helper-text {
  font-size: 0.85rem;
}
.helper-text-error {
  color: #b91c1c;
}
.helper-text-warn {
  color: #92400e;
}
.actions {
  display: flex;
  justify-content: flex-end;
}
.btn-primary {
  padding: 0.5rem 1rem;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary[disabled] {
  background: #d1d5db;
  cursor: not-allowed;
}
</style>
