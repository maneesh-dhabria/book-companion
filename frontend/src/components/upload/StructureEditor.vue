<script setup lang="ts">
/**
 * StructureEditor — shared section editor used by:
 *   - mode='wizard'        (step 2 of UploadWizard, before any summary exists)
 *   - mode='post-summary'  (EditStructureView, may invalidate existing summaries)
 *
 * Capabilities (T20 / FR-F4..F11):
 *   - Multi-select with shift-range and ctrl/meta-toggle
 *   - HTML5 native drag-reorder; Alt+ArrowUp/Down keyboard reorder
 *   - Inline rename (validated 1..500 chars)
 *   - Delete with 5s undo (per-row independent)
 *   - Bulk delete (disabled if it would empty the book)
 *   - Merge selected (>=2)
 *   - Split single (opens SplitModal)
 *   - In post-summary mode: confirm with edit-impact before persisting
 */
import { computed, onMounted, ref } from 'vue'

import {
  deleteSection,
  getEditImpact,
  listSections,
  mergeSections,
  patchSection,
  reorderSections,
} from '@/api/sections'
import type { Section } from '@/types'

import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import SplitModal from './SplitModal.vue'

const props = defineProps<{
  bookId: number
  mode: 'wizard' | 'post-summary'
}>()

const emit = defineEmits<{
  complete: []
  back: []
}>()

const sections = ref<Section[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const selected = ref<Set<number>>(new Set())
const lastClicked = ref<number | null>(null)
const editingId = ref<number | null>(null)
const editingTitle = ref('')
const renameError = ref<string | null>(null)
const splitModalSectionId = ref<number | null>(null)

interface UndoRow {
  section: Section
  index: number
  expiresAt: number
  timer: number
}
const undoStack = ref<UndoRow[]>([])

const confirmOpen = ref(false)
const confirmAction = ref<(() => Promise<void>) | null>(null)
const confirmCopy = ref<{ title: string; message: string }>({ title: '', message: '' })

const canBulkDelete = computed(
  () => selected.value.size > 0 && selected.value.size < sections.value.length,
)
const canMerge = computed(() => selected.value.size >= 2)
const canSplit = computed(() => selected.value.size === 1)

async function load() {
  loading.value = true
  error.value = null
  try {
    sections.value = await listSections(props.bookId)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)

function clickRow(id: number, e: MouseEvent) {
  if (e.shiftKey && lastClicked.value !== null) {
    const a = sections.value.findIndex((s) => s.id === lastClicked.value)
    const b = sections.value.findIndex((s) => s.id === id)
    if (a >= 0 && b >= 0) {
      const [lo, hi] = a < b ? [a, b] : [b, a]
      const next = new Set(selected.value)
      for (let i = lo; i <= hi; i++) next.add(sections.value[i].id)
      selected.value = next
    }
  } else if (e.metaKey || e.ctrlKey) {
    const next = new Set(selected.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    selected.value = next
  } else {
    selected.value = new Set([id])
  }
  lastClicked.value = id
}

function startRename(section: Section) {
  editingId.value = section.id
  editingTitle.value = section.title
  renameError.value = null
}

function cancelRename() {
  editingId.value = null
  renameError.value = null
}

async function commitRename() {
  if (editingId.value === null) return
  const title = editingTitle.value.trim()
  if (!title) {
    renameError.value = 'Title cannot be empty'
    return
  }
  if (title.length > 500) {
    renameError.value = 'Title must be 500 characters or less'
    return
  }
  try {
    const updated = await patchSection(props.bookId, editingId.value, { title })
    const idx = sections.value.findIndex((s) => s.id === editingId.value)
    if (idx >= 0) sections.value[idx] = { ...sections.value[idx], title: updated.title }
    cancelRename()
  } catch (e) {
    renameError.value = (e as Error).message
  }
}

// ── Drag reorder ──────────────────────────────────────────────────────────
const draggingId = ref<number | null>(null)

function onDragStart(id: number, e: DragEvent) {
  draggingId.value = id
  e.dataTransfer?.setData('text/plain', String(id))
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
}

async function onDrop(targetId: number, e: DragEvent) {
  e.preventDefault()
  const src = draggingId.value
  draggingId.value = null
  if (src === null || src === targetId) return
  const fromIdx = sections.value.findIndex((s) => s.id === src)
  const toIdx = sections.value.findIndex((s) => s.id === targetId)
  if (fromIdx < 0 || toIdx < 0) return
  const next = sections.value.slice()
  const [moved] = next.splice(fromIdx, 1)
  next.splice(toIdx, 0, moved)
  sections.value = next
  await persistOrder()
}

async function keyboardReorder(id: number, dir: -1 | 1) {
  const idx = sections.value.findIndex((s) => s.id === id)
  const tgt = idx + dir
  if (idx < 0 || tgt < 0 || tgt >= sections.value.length) return
  const next = sections.value.slice()
  const [moved] = next.splice(idx, 1)
  next.splice(tgt, 0, moved)
  sections.value = next
  await persistOrder()
}

async function persistOrder() {
  if (props.mode === 'post-summary') {
    const ok = await confirmIfImpactful(
      sections.value.map((s) => s.id),
      'Reorder sections?',
      'Reordering will reset the book-level summary. Section summaries are kept.',
    )
    if (!ok) {
      await load()
      return
    }
  }
  try {
    sections.value = await reorderSections(
      props.bookId,
      sections.value.map((s) => s.id),
    )
  } catch (e) {
    error.value = (e as Error).message
    await load()
  }
}

// ── Delete with 5s undo ───────────────────────────────────────────────────
function deleteOne(id: number) {
  const idx = sections.value.findIndex((s) => s.id === id)
  if (idx < 0) return
  const sec = sections.value[idx]
  // Optimistic remove from view; actual API call deferred until undo expires.
  sections.value = sections.value.filter((s) => s.id !== id)
  selected.value.delete(id)
  const expiresAt = Date.now() + 5000
  const timer = window.setTimeout(() => commitDelete(id), 5000)
  undoStack.value = [...undoStack.value, { section: sec, index: idx, expiresAt, timer }]
}

async function commitDelete(id: number) {
  const row = undoStack.value.find((r) => r.section.id === id)
  if (!row) return
  undoStack.value = undoStack.value.filter((r) => r.section.id !== id)
  if (props.mode === 'post-summary') {
    const ok = await confirmIfImpactful(
      [id],
      `Delete "${row.section.title}"?`,
      undefined,
    )
    if (!ok) {
      // restore
      sections.value = sortByOrder([...sections.value, row.section])
      return
    }
  }
  try {
    await deleteSection(props.bookId, id)
  } catch (e) {
    error.value = (e as Error).message
    sections.value = sortByOrder([...sections.value, row.section])
  }
}

function undoDelete(id: number) {
  const row = undoStack.value.find((r) => r.section.id === id)
  if (!row) return
  window.clearTimeout(row.timer)
  undoStack.value = undoStack.value.filter((r) => r.section.id !== id)
  sections.value = sortByOrder([...sections.value, row.section])
}

function sortByOrder(arr: Section[]): Section[] {
  return [...arr].sort((a, b) => a.order_index - b.order_index)
}

// ── Bulk delete / Merge / Split ───────────────────────────────────────────
function bulkDeleteSelected() {
  const ids = Array.from(selected.value)
  selected.value = new Set()
  ids.forEach(deleteOne)
}

async function mergeSelected() {
  if (!canMerge.value) return
  const ids = Array.from(selected.value).sort((a, b) => {
    const ai = sections.value.findIndex((s) => s.id === a)
    const bi = sections.value.findIndex((s) => s.id === b)
    return ai - bi
  })
  const title = window.prompt('Title for the merged section:')
  if (!title || !title.trim()) return
  if (props.mode === 'post-summary') {
    const ok = await confirmIfImpactful(
      ids,
      `Merge ${ids.length} sections?`,
      undefined,
    )
    if (!ok) return
  }
  try {
    await mergeSections(props.bookId, ids, title.trim())
    selected.value = new Set()
    await load()
  } catch (e) {
    error.value = (e as Error).message
  }
}

function openSplitForSelected() {
  if (selected.value.size !== 1) return
  splitModalSectionId.value = Array.from(selected.value)[0]!
}

async function onSplitDone() {
  splitModalSectionId.value = null
  selected.value = new Set()
  await load()
}

// ── Edit-impact confirmation (post-summary only) ──────────────────────────
async function confirmIfImpactful(
  sectionIds: number[],
  title: string,
  fallbackMessage: string | undefined,
): Promise<boolean> {
  try {
    const impact = await getEditImpact(props.bookId, sectionIds)
    if (
      impact.summarized_section_count === 0 &&
      !impact.invalidate_book_summary
    ) {
      return true
    }
    return await new Promise<boolean>((resolve) => {
      const parts: string[] = []
      if (impact.summarized_section_count > 0) {
        parts.push(
          `${impact.summarized_section_count} section ${
            impact.summarized_section_count === 1 ? 'summary' : 'summaries'
          } will be marked stale.`,
        )
      }
      if (impact.invalidate_book_summary) {
        parts.push('The book summary will be cleared.')
      }
      if (parts.length === 0 && fallbackMessage) parts.push(fallbackMessage)
      confirmCopy.value = {
        title,
        message: parts.join(' '),
      }
      confirmAction.value = async () => {
        confirmOpen.value = false
        resolve(true)
      }
      confirmOpen.value = true
      const onCancel = () => {
        confirmOpen.value = false
        resolve(false)
      }
      // attach cancel via our dialog component handler — we resolve(false)
      // when user clicks Cancel; the dialog emits the event. We pipe that
      // through `confirmAction` only on confirm; cancel lives below.
      pendingCancel.value = onCancel
    })
  } catch {
    // If preflight fails, allow the action; backend will still validate.
    return true
  }
}

const pendingCancel = ref<(() => void) | null>(null)
async function onConfirmOk() {
  if (confirmAction.value) await confirmAction.value()
  confirmAction.value = null
  pendingCancel.value = null
}
function onConfirmCancel() {
  if (pendingCancel.value) pendingCancel.value()
  confirmOpen.value = false
  confirmAction.value = null
  pendingCancel.value = null
}
</script>

<template>
  <div class="space-y-3" data-testid="structure-editor">
    <header class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {{ mode === 'wizard' ? 'Review structure' : 'Edit structure' }}
        </h2>
        <p class="text-sm text-stone-500 dark:text-stone-400">
          {{ sections.length }} section{{ sections.length === 1 ? '' : 's' }}.
          {{ selected.size > 0 ? `${selected.size} selected.` : '' }}
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-md border border-stone-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-stone-600"
          :disabled="!canMerge"
          data-testid="merge-btn"
          @click="mergeSelected"
        >
          Merge
        </button>
        <button
          type="button"
          class="rounded-md border border-stone-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-stone-600"
          :disabled="!canSplit"
          data-testid="split-btn"
          @click="openSplitForSelected"
        >
          Split
        </button>
        <button
          type="button"
          class="rounded-md border border-red-300 px-3 py-1 text-sm text-red-700 disabled:opacity-50 dark:border-red-700 dark:text-red-300"
          :disabled="!canBulkDelete"
          data-testid="bulk-delete-btn"
          @click="bulkDeleteSelected"
        >
          Delete selected
        </button>
      </div>
    </header>

    <div v-if="error" class="rounded-md bg-red-50 p-2 text-sm text-red-700">
      {{ error }}
    </div>

    <ul
      v-if="!loading"
      class="overflow-hidden rounded-md border border-stone-200 dark:border-stone-700"
      data-testid="section-list"
    >
      <li
        v-for="section in sections"
        :key="section.id"
        :class="[
          'flex items-center gap-3 border-b border-stone-100 px-3 py-2 last:border-b-0 dark:border-stone-800',
          selected.has(section.id) ? 'bg-blue-50 dark:bg-blue-900/20' : '',
          draggingId === section.id ? 'opacity-50' : '',
        ]"
        :data-section-id="section.id"
        draggable="true"
        @click="(e) => clickRow(section.id, e)"
        @keydown.alt.up.prevent="keyboardReorder(section.id, -1)"
        @keydown.alt.down.prevent="keyboardReorder(section.id, 1)"
        @dragstart="(e) => onDragStart(section.id, e)"
        @dragover="onDragOver"
        @drop="(e) => onDrop(section.id, e)"
        tabindex="0"
      >
        <span class="w-8 text-xs text-stone-500 dark:text-stone-400">
          {{ section.order_index + 1 }}
        </span>
        <span
          class="cursor-grab text-stone-400 select-none"
          aria-hidden="true"
          title="Drag to reorder"
          >⋮⋮</span
        >
        <div class="min-w-0 flex-1">
          <div v-if="editingId === section.id" class="flex items-center gap-2">
            <input
              v-model="editingTitle"
              class="flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm dark:border-stone-600 dark:bg-stone-900"
              :data-testid="`rename-input-${section.id}`"
              @keydown.enter.prevent="commitRename"
              @keydown.esc.prevent="cancelRename"
            />
            <button
              type="button"
              class="rounded-md bg-blue-600 px-2 py-1 text-xs text-white"
              @click.stop="commitRename"
            >
              Save
            </button>
            <button
              type="button"
              class="text-xs text-stone-500"
              @click.stop="cancelRename"
            >
              Cancel
            </button>
            <span
              v-if="renameError"
              class="text-xs text-red-600 dark:text-red-400"
              data-testid="rename-error"
              >{{ renameError }}</span
            >
          </div>
          <div v-else class="flex items-baseline gap-2">
            <span class="truncate font-medium text-stone-900 dark:text-stone-100">
              {{ section.title }}
            </span>
            <span class="text-xs text-stone-400 dark:text-stone-500">{{ section.section_type }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <button
            type="button"
            class="text-stone-500 hover:text-stone-900 dark:hover:text-stone-100"
            @click.stop="startRename(section)"
          >
            Rename
          </button>
          <button
            type="button"
            class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
            :data-testid="`delete-${section.id}`"
            @click.stop="deleteOne(section.id)"
          >
            Delete
          </button>
        </div>
      </li>
    </ul>

    <div v-if="undoStack.length > 0" class="space-y-1" data-testid="undo-stack">
      <div
        v-for="row in undoStack"
        :key="row.section.id"
        class="flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm dark:border-amber-700 dark:bg-amber-900/30"
      >
        <span>Deleted "{{ row.section.title }}"</span>
        <button
          type="button"
          class="text-sm font-medium text-amber-800 hover:underline dark:text-amber-200"
          @click="undoDelete(row.section.id)"
        >
          Undo
        </button>
      </div>
    </div>

    <footer class="flex justify-between">
      <button
        type="button"
        class="rounded-md border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600"
        @click="$emit('back')"
      >
        Back
      </button>
      <button
        type="button"
        class="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        data-testid="structure-continue"
        @click="$emit('complete')"
      >
        {{ mode === 'wizard' ? 'Continue' : 'Done' }}
      </button>
    </footer>

    <SplitModal
      v-if="splitModalSectionId !== null"
      :book-id="bookId"
      :section-id="splitModalSectionId"
      :open="splitModalSectionId !== null"
      @close="splitModalSectionId = null"
      @split="onSplitDone"
    />

    <ConfirmDialog
      :open="confirmOpen"
      :title="confirmCopy.title"
      :message="confirmCopy.message"
      tone="danger"
      confirm-label="Proceed"
      @confirm="onConfirmOk"
      @cancel="onConfirmCancel"
    />
  </div>
</template>
