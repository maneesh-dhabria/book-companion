<template>
  <div class="spot-error">
    <div data-test="intended-error-callout" class="callout">
      <span class="badge">Wrong restatement</span>
      <p class="text">{{ intendedError }}</p>
    </div>
    <label class="label">Write the corrected version:</label>
    <textarea
      data-test="correction-input"
      class="correction"
      :value="modelValue"
      rows="4"
      placeholder="Explain why the restatement is wrong and write the correct version…"
      @input="onInput"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{ intendedError: string; modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}
</script>

<style scoped>
.spot-error {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.callout {
  padding: 0.7rem 0.85rem;
  background: #fef3c7;
  border-left: 3px solid #d97706;
  border-radius: 4px;
}
.badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #92400e;
  margin-bottom: 0.3rem;
}
.text {
  margin: 0;
  font-size: 0.95rem;
  color: #78350f;
}
.label {
  font-size: 0.85rem;
  font-weight: 500;
  color: #374151;
}
.correction {
  width: 100%;
  min-height: 6rem;
  padding: 0.6rem 0.7rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.95rem;
  font-family: inherit;
  resize: vertical;
}
.correction:focus {
  outline: 2px solid #4f46e5;
  outline-offset: 1px;
}
</style>
