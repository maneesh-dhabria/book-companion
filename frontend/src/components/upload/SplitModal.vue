<script setup lang="ts">
/**
 * Three-mode split modal (T21 / FR-B18a).
 *
 * Modes:
 *   - heading: Markdown # boundaries
 *   - paragraph: blank-line splits
 *   - char: single boundary at user-picked position
 *
 * Shows live previews from GET /sections/{id}/split-preview before the
 * commit, then calls POST /sections/{id}/split on confirm.
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  getSplitPreview,
  splitSection,
  type SplitPreviewCandidate,
} from '@/api/sections'

const props = defineProps<{
  bookId: number
  sectionId: number
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  split: []
}>()

type Mode = 'heading' | 'paragraph' | 'char'
const mode = ref<Mode>('heading')
const charPosition = ref<number>(500)
const candidates = ref<SplitPreviewCandidate[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const submitting = ref(false)

async function loadPreview() {
  if (!props.open) return
  loading.value = true
  error.value = null
  try {
    const resp = await getSplitPreview(
      props.bookId,
      props.sectionId,
      mode.value,
      mode.value === 'char' ? charPosition.value : undefined,
    )
    candidates.value = resp.candidates
  } catch (e) {
    error.value = (e as Error).message
    candidates.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.open, props.sectionId, mode.value], loadPreview, { immediate: false })
watch(charPosition, () => {
  if (mode.value === 'char') void loadPreview()
})

onMounted(() => {
  if (props.open) void loadPreview()
})

const canSubmit = computed(
  () => candidates.value.length >= 2 && !loading.value && !submitting.value,
)

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    // Positions are the START offsets of every candidate after the first;
    // the backend SectionEditService accepts that shape.
    const positions = candidates.value.slice(1).map((c) => c.start)
    await splitSection(props.bookId, props.sectionId, mode.value, positions)
    emit('split')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Transition name="fade">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      data-testid="split-modal"
      @click.self="$emit('close')"
    >
      <div
        class="w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl dark:bg-stone-800"
      >
        <header class="border-b border-stone-200 px-5 py-3 dark:border-stone-700">
          <h3 class="text-lg font-medium text-stone-900 dark:text-stone-100">
            Split section
          </h3>
        </header>

        <div class="space-y-4 px-5 py-4">
          <div class="flex gap-2">
            <button
              v-for="m in ['heading', 'paragraph', 'char'] as Mode[]"
              :key="m"
              type="button"
              :class="[
                'rounded-md border px-3 py-1.5 text-sm capitalize',
                mode === m
                  ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  : 'border-stone-300 hover:bg-stone-50 dark:border-stone-600 dark:hover:bg-stone-700',
              ]"
              :data-testid="`split-mode-${m}`"
              @click="mode = m"
            >
              {{ m }}
            </button>
          </div>

          <div v-if="mode === 'char'" class="flex items-center gap-2 text-sm">
            <label for="char-pos" class="font-medium">Position:</label>
            <input
              id="char-pos"
              v-model.number="charPosition"
              type="number"
              min="1"
              class="w-24 rounded-md border border-stone-300 px-2 py-1 text-sm dark:border-stone-600 dark:bg-stone-900"
              data-testid="char-position-input"
            />
            <span class="text-stone-500 dark:text-stone-400">characters from start</span>
          </div>

          <div
            v-if="error"
            class="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300"
            data-testid="split-error"
          >
            {{ error }}
          </div>

          <div v-if="loading" class="text-sm text-stone-500" data-testid="split-loading">
            Computing preview…
          </div>

          <div
            v-else-if="candidates.length === 0"
            class="rounded-md bg-amber-50 p-3 text-sm text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
          >
            No split boundaries found in this mode.
          </div>

          <ol
            v-else
            class="max-h-72 space-y-2 overflow-y-auto rounded-md border border-stone-200 p-2 dark:border-stone-700"
            data-testid="split-candidates"
          >
            <li
              v-for="(c, idx) in candidates"
              :key="`${idx}-${c.start}`"
              class="rounded-md border border-stone-200 p-2 text-sm dark:border-stone-700"
            >
              <div class="font-medium text-stone-900 dark:text-stone-100">
                {{ c.title }}
              </div>
              <div class="text-xs text-stone-500 dark:text-stone-400">
                {{ c.char_count }} chars
              </div>
              <div
                class="mt-1 truncate text-stone-600 dark:text-stone-300"
                :title="c.first_line"
              >
                {{ c.first_line }}
              </div>
            </li>
          </ol>
        </div>

        <footer
          class="flex justify-end gap-2 border-t border-stone-200 bg-stone-50 px-5 py-3 dark:border-stone-700 dark:bg-stone-900"
        >
          <button
            type="button"
            class="rounded-md border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600"
            @click="$emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="!canSubmit"
            data-testid="split-submit"
            @click="submit"
          >
            {{ submitting ? 'Splitting…' : `Split into ${candidates.length}` }}
          </button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
