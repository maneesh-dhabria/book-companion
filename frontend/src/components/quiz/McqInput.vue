<template>
  <div class="mcq" role="radiogroup">
    <button
      v-for="(opt, idx) in options"
      :key="idx"
      type="button"
      data-test="mcq-option"
      class="mcq-option"
      :class="{ selected: selectedIndex === idx }"
      :aria-pressed="selectedIndex === idx"
      @click="onPick(idx)"
    >
      <span class="letter">{{ String.fromCharCode(65 + idx) }}.</span>
      <span class="text">{{ opt }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ options: string[]; selectedIndex: number | null }>()
const emit = defineEmits<{ (e: 'select', idx: number): void }>()

function onPick(idx: number) {
  emit('select', idx)
}
</script>

<style scoped>
.mcq {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.mcq-option {
  text-align: left;
  padding: 0.65rem 0.85rem;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95rem;
  display: flex;
  gap: 0.6rem;
}
.mcq-option:hover {
  background: #f9fafb;
}
.mcq-option.selected {
  border-color: #4f46e5;
  background: #eef2ff;
}
.letter {
  font-weight: 600;
  color: #4f46e5;
}
</style>
