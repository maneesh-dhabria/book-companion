<template>
  <div class="tag-chip-input">
    <TagChip
      v-for="t in modelValue"
      :key="t"
      :label="t"
      removable
      @remove="remove(t)"
    />
    <button
      v-if="!editing"
      type="button"
      class="add-tag-btn"
      @click="enterEdit"
    >
      + Add tag
    </button>
    <div v-else class="input-wrap" aria-live="polite">
      <input
        ref="inputEl"
        v-model="query"
        type="text"
        :placeholder="placeholder"
        class="chip-field"
        aria-label="Add a tag"
        @keydown.enter.prevent="commit(query)"
        @keydown.escape.prevent="onEsc"
        @keydown.backspace="backspace"
        @input="onQueryInput"
        @blur="onBlur"
      />
      <ul v-if="suggestions.length" class="suggest-list" role="listbox">
        <li
          v-for="s in suggestions"
          :key="s"
          role="option"
          tabindex="0"
          @mousedown.prevent="commit(s)"
        >
          {{ s }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'

import TagChip from './TagChip.vue'
import { useDebounceFn } from '@/composables/useDebounceFn'
import { useUiStore } from '@/stores/ui'

const MAX_TAG_LEN = 64

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    suggest?: (q: string) => Promise<string[]>
    placeholder?: string
    minSuggestChars?: number
  }>(),
  { placeholder: 'Add tag…', minSuggestChars: 2 },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const query = ref('')
const suggestions = ref<string[]>([])
const inputEl = ref<HTMLInputElement | null>(null)
const editing = ref(false)

const runSuggest = useDebounceFn(async (q: string) => {
  if (!props.suggest || q.length < props.minSuggestChars) {
    suggestions.value = []
    return
  }
  try {
    const res = await props.suggest(q)
    suggestions.value = res.filter((s) => !props.modelValue.includes(s))
  } catch {
    suggestions.value = []
  }
}, 150)

function enterEdit() {
  editing.value = true
  void nextTick(() => inputEl.value?.focus())
}

function onQueryInput() {
  runSuggest(query.value.trim())
}

function commit(raw: string) {
  let name = raw.trim().replace(/\s+/g, ' ')
  if (!name) return
  if (name.length > MAX_TAG_LEN) {
    name = name.slice(0, MAX_TAG_LEN)
    useUiStore().showToast('Tag truncated to 64 characters', 'warning')
  }
  if (props.modelValue.includes(name)) {
    query.value = ''
    suggestions.value = []
    return
  }
  emit('update:modelValue', [...props.modelValue, name])
  query.value = ''
  suggestions.value = []
  // FR-F3.3: stay in edit mode after Enter so the user can keep adding.
}

function remove(tag: string) {
  emit(
    'update:modelValue',
    props.modelValue.filter((t) => t !== tag),
  )
}

function backspace(e: KeyboardEvent) {
  if (query.value === '' && props.modelValue.length) {
    e.preventDefault()
    remove(props.modelValue[props.modelValue.length - 1])
  }
}

function onEsc() {
  query.value = ''
  suggestions.value = []
  editing.value = false
}

function onBlur() {
  // Defer to next tick so a click on a suggestion (which uses
  // mousedown.prevent + commit) can still complete.
  void nextTick(() => {
    if (!editing.value) return
    const text = query.value.trim()
    if (text) {
      commit(text)
    }
    editing.value = false
  })
}
</script>

<style scoped>
.tag-chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}
.add-tag-btn {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 0.875rem;
  padding: 0.15rem 0.25rem;
  cursor: pointer;
}
.add-tag-btn:hover {
  color: #374151;
}
.input-wrap {
  position: relative;
  flex: 1;
  min-width: 8rem;
}
.chip-field {
  border: 0;
  border-bottom: 1px solid #d1d5db;
  outline: none;
  padding: 0.2rem 0.25rem;
  font-size: 0.875rem;
  width: 100%;
  background: transparent;
}
.chip-field:focus {
  border-bottom-color: #2563eb;
}
.suggest-list {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  right: 0;
  margin: 0.25rem 0 0;
  padding: 0.25rem 0;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  list-style: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  max-height: 12rem;
  overflow-y: auto;
}
.suggest-list li {
  padding: 0.35rem 0.65rem;
  font-size: 0.875rem;
  cursor: pointer;
}
.suggest-list li:hover {
  background: #f3f4f6;
}
</style>
