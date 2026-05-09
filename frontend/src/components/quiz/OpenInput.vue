<template>
  <textarea
    ref="taRef"
    data-test="open-input"
    class="open-input"
    :value="modelValue"
    rows="4"
    placeholder="Type your answer…"
    @input="onInput"
  />
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const taRef = ref<HTMLTextAreaElement | null>(null)

function autosize() {
  const el = taRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

function onInput(e: Event) {
  const v = (e.target as HTMLTextAreaElement).value
  emit('update:modelValue', v)
  nextTick(autosize)
}

watch(
  () => props.modelValue,
  () => nextTick(autosize),
)
</script>

<style scoped>
.open-input {
  width: 100%;
  min-height: 6rem;
  padding: 0.6rem 0.7rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.95rem;
  font-family: inherit;
  resize: vertical;
}
.open-input:focus {
  outline: 2px solid #4f46e5;
  outline-offset: 1px;
}
</style>
