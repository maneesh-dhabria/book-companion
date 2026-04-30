<script setup lang="ts">
const props = defineProps<{
  modelValue: number
  step: number
  format: (v: number) => string
  ariaLabel: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', v: number): void }>()

function dec() {
  emit('update:modelValue', props.modelValue - props.step)
}
function inc() {
  emit('update:modelValue', props.modelValue + props.step)
}
</script>

<template>
  <div class="stepper">
    <button type="button" :aria-label="`Decrease ${ariaLabel}`" @click="dec">−</button>
    <span>{{ format(modelValue) }}</span>
    <button type="button" :aria-label="`Increase ${ariaLabel}`" @click="inc">+</button>
  </div>
</template>

<style scoped>
.stepper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.stepper button {
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  background: var(--color-bg, #fff);
  cursor: pointer;
}
.stepper span {
  font-size: 0.875rem;
  min-width: 3rem;
  text-align: center;
}
</style>
