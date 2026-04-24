<template>
  <div class="tag-chip-input">
    <TagChip
      v-for="t in modelValue"
      :key="t"
      :label="t"
      removable
      @remove="remove(t)"
    />
    <div class="input-wrap">
      <input
        ref="inputEl"
        v-model="query"
        type="text"
        :placeholder="placeholder"
        class="chip-field"
        @keydown.enter.prevent="commit(query)"
        @keydown.backspace="backspace"
        @input="onQueryInput"
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
import { ref } from 'vue'
import TagChip from './TagChip.vue'
import { useDebounceFn } from '@/composables/useDebounceFn'

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

function onQueryInput() {
  runSuggest(query.value.trim())
}

function commit(raw: string) {
  const name = raw.trim().replace(/\s+/g, ' ')
  if (!name) return
  if (props.modelValue.includes(name)) {
    query.value = ''
    suggestions.value = []
    return
  }
  emit('update:modelValue', [...props.modelValue, name])
  query.value = ''
  suggestions.value = []
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
</script>

<style scoped>
.tag-chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  padding: 0.35rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
}
.input-wrap {
  position: relative;
  flex: 1;
  min-width: 8rem;
}
.chip-field {
  border: 0;
  outline: none;
  padding: 0.25rem 0.35rem;
  font-size: 0.875rem;
  width: 100%;
  background: transparent;
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
