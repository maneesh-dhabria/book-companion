<template>
  <label class="theme-input" data-test="theme-input">
    <span class="label-text">Theme (optional)</span>
    <textarea
      :value="modelValue ?? ''"
      :maxlength="maxChars"
      :placeholder="placeholder"
      rows="2"
      @input="onInput"
    />
    <span class="counter">{{ (modelValue ?? '').length }} / {{ maxChars }}</span>
  </label>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: string | null
  maxChars?: number
  placeholder?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const maxChars = props.maxChars ?? 200
const placeholder = props.placeholder ?? 'e.g. behavioural-finance applications'

function onInput(e: Event) {
  const v = (e.target as HTMLTextAreaElement).value
  emit('update:modelValue', v.length === 0 ? null : v)
}
</script>

<style scoped>
.theme-input {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin: 0.5rem 0;
}
.theme-input textarea {
  width: 100%;
  font-family: inherit;
  padding: 0.5rem;
  border: 1px solid var(--color-border, #ccc);
  border-radius: 4px;
}
.theme-input .counter {
  align-self: flex-end;
  font-size: 0.8rem;
  color: var(--color-text-muted, #666);
}
</style>
