<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useUiStore } from '@/stores/ui'
import { exportBookSummary, type SummaryExportSelection } from '@/api/export'

interface SectionLite {
  id: number
  title: string
  has_summary: boolean
}

interface BookForExport {
  id: number
  default_summary_id: number | null
  default_summary?: unknown
  sections: SectionLite[]
}

const props = defineProps<{ bookId: number; book: BookForExport }>()
const emit = defineEmits<{ close: [] }>()

const ui = useUiStore()
const refreshing = ref(true)
const refreshFailed = ref(false)
const sections = ref<SectionLite[]>(props.book.sections || [])
const totalCount = computed(() => sections.value.length)
const summarized = computed(() => sections.value.filter((s) => s.has_summary))
const summarizedCount = computed(() => summarized.value.length)
const hiddenCount = computed(() => totalCount.value - summarizedCount.value)

const hasBookSummary = computed(
  () =>
    !!props.book.default_summary_id || !!props.book.default_summary,
)
const includeBookSummary = ref(hasBookSummary.value)
const includeToc = ref(true)
const includeAnnotations = ref(true)
const checkedSectionIds = ref<Set<number>>(
  new Set(summarized.value.map((s) => s.id)),
)

const masterChecked = computed(
  () =>
    summarizedCount.value > 0 &&
    checkedSectionIds.value.size === summarizedCount.value,
)
const masterIndeterminate = computed(
  () => checkedSectionIds.value.size > 0 && !masterChecked.value,
)

const masterEl = ref<HTMLInputElement | null>(null)
watch([masterIndeterminate, masterEl], () => {
  if (masterEl.value) masterEl.value.indeterminate = masterIndeterminate.value
})

function toggleMaster() {
  if (masterChecked.value) {
    checkedSectionIds.value = new Set()
  } else {
    checkedSectionIds.value = new Set(summarized.value.map((s) => s.id))
  }
}

function isChecked(id: number) {
  return checkedSectionIds.value.has(id)
}
function setChecked(id: number, val: boolean | Event) {
  const v = typeof val === 'boolean' ? val : (val.target as HTMLInputElement).checked
  const next = new Set(checkedSectionIds.value)
  if (v) next.add(id)
  else next.delete(id)
  checkedSectionIds.value = next
}

const exporting = ref(false)
const submitDisabled = computed(() => exporting.value)

function buildSelection(): SummaryExportSelection {
  const excluded = summarized.value
    .filter((s) => !checkedSectionIds.value.has(s.id))
    .map((s) => s.id)
  return {
    include_book_summary: includeBookSummary.value,
    include_toc: includeToc.value,
    include_annotations: includeAnnotations.value,
    exclude_section_ids: excluded,
  }
}

async function onExport() {
  exporting.value = true
  try {
    const r = await exportBookSummary(props.bookId, buildSelection())
    const url = URL.createObjectURL(r.blob)
    const a = document.createElement('a')
    a.href = url
    a.download = r.filename
    a.click()
    URL.revokeObjectURL(url)
    ui.showToast(
      r.isEmpty ? 'Summary exported (empty)' : `Summary exported as ${r.filename}`,
      'success',
    )
    emit('close')
  } catch {
    ui.showToast('Export failed -- check your connection.', 'error')
  } finally {
    exporting.value = false
  }
}

async function onCopy() {
  exporting.value = true
  try {
    const r = await exportBookSummary(props.bookId, buildSelection())
    try {
      await navigator.clipboard.writeText(r.text)
      ui.showToast(
        r.isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
        'success',
      )
      emit('close')
    } catch {
      ui.showToast("Couldn't copy -- try Export instead.", 'error')
    }
  } catch {
    ui.showToast('Export failed -- check your connection.', 'error')
  } finally {
    exporting.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  refreshing.value = true
  try {
    const r = await fetch(`/api/v1/books/${props.bookId}`)
    if (!r.ok) throw new Error('refresh failed')
    const fresh = await r.json()
    sections.value = fresh.sections || []
    checkedSectionIds.value = new Set(
      (fresh.sections || [])
        .filter((s: SectionLite) => s.has_summary)
        .map((s: SectionLite) => s.id),
    )
  } catch {
    refreshFailed.value = true
  } finally {
    refreshing.value = false
  }
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div
    class="modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="export-modal-title"
    @click.self="emit('close')"
  >
    <div class="modal-body">
      <h3 id="export-modal-title" class="modal-title">Export summary</h3>

      <div v-if="refreshing" class="loading">Refreshing sections…</div>
      <p v-if="refreshFailed" class="refresh-warning">
        Could not refresh -- showing cached sections.
      </p>

      <fieldset class="toggles" :disabled="refreshing">
        <label>
          <input
            type="checkbox"
            data-testid="toggle-book-summary"
            v-model="includeBookSummary"
            :disabled="!hasBookSummary"
          />
          Book summary
          <span v-if="!hasBookSummary" class="muted">
            -- no book summary yet
          </span>
        </label>
        <label>
          <input type="checkbox" data-testid="toggle-toc" v-model="includeToc" />
          Table of contents
        </label>
        <label>
          <input
            type="checkbox"
            data-testid="toggle-annotations"
            v-model="includeAnnotations"
          />
          Highlights &amp; notes
        </label>
        <label class="sections-master">
          <input
            ref="masterEl"
            type="checkbox"
            data-testid="sections-master"
            :checked="masterChecked"
            @click.prevent="toggleMaster"
          />
          Sections
        </label>
      </fieldset>

      <ul class="section-list">
        <li v-for="s in summarized" :key="s.id" data-testid="section-checkbox-row">
          <label>
            <input
              type="checkbox"
              :data-testid="`section-checkbox-${s.id}`"
              :checked="isChecked(s.id)"
              @change="setChecked(s.id, $event)"
            />
            {{ s.title }}
          </label>
        </li>
        <li v-if="summarized.length === 0" class="muted">
          No sections found in this book.
        </li>
      </ul>
      <p class="count-footer">
        {{ summarizedCount }} of {{ totalCount }} sections summarized<span
          v-if="hiddenCount > 0"
        >
          -- {{ hiddenCount }} hidden because they have no summary</span
        >
      </p>

      <div class="modal-actions">
        <button
          type="button"
          class="secondary-btn"
          @click="emit('close')"
          :disabled="exporting"
        >
          Cancel
        </button>
        <button
          type="button"
          class="primary-btn"
          data-testid="modal-export-btn"
          :disabled="submitDisabled"
          @click="onExport"
        >
          {{ exporting ? 'Exporting…' : 'Export' }}
        </button>
        <button
          type="button"
          class="primary-btn"
          data-testid="modal-copy-btn"
          :disabled="submitDisabled"
          @click="onCopy"
        >
          {{ exporting ? 'Copying…' : 'Copy as Markdown' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal-body {
  width: min(560px, 92vw);
  max-height: 90vh;
  overflow: auto;
  background: var(--color-bg-primary, #fff);
  color: var(--color-text-primary, #111);
  border-radius: 0.75rem;
  padding: 1.25rem;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.modal-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}
.toggles {
  border: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.toggles label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
}
.sections-master {
  font-weight: 600;
}
.section-list {
  list-style: none;
  padding: 0 0 0 1.25rem;
  margin: 0;
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}
.count-footer {
  font-size: 0.8rem;
  color: #6b7280;
  margin: 0;
}
.muted {
  color: #6b7280;
  font-size: 0.85rem;
}
.refresh-warning {
  background: #fff7ed;
  border: 1px solid #fdba74;
  padding: 0.4rem 0.6rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;
}
.loading {
  font-size: 0.85rem;
  color: #6b7280;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.primary-btn {
  padding: 0.5rem 1rem;
  background: var(--color-primary, #3b82f6);
  color: white;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.secondary-btn {
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  background: none;
  color: inherit;
  cursor: pointer;
}
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
