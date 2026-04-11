<script setup lang="ts">
defineProps<{
  steps: string[]
  current: number
}>()
</script>

<template>
  <div class="step-indicator">
    <div
      v-for="(step, index) in steps"
      :key="index"
      class="step"
      :class="{ active: index + 1 === current, completed: index + 1 < current }"
    >
      <div class="step-number">
        <span v-if="index + 1 < current">✓</span>
        <span v-else>{{ index + 1 }}</span>
      </div>
      <span class="step-label">{{ step }}</span>
      <div v-if="index < steps.length - 1" class="step-connector" />
    </div>
  </div>
</template>

<style scoped>
.step-indicator { display: flex; align-items: center; justify-content: center; gap: 0; }
.step { display: flex; align-items: center; gap: 0.375rem; }
.step-number { width: 1.75rem; height: 1.75rem; border-radius: 50%; border: 2px solid var(--color-border, #ddd); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; color: var(--color-text-secondary, #888); }
.step.active .step-number { border-color: var(--color-primary, #3b82f6); background: var(--color-primary, #3b82f6); color: #fff; }
.step.completed .step-number { border-color: var(--color-success, #22c55e); background: var(--color-success, #22c55e); color: #fff; }
.step-label { font-size: 0.75rem; font-weight: 500; color: var(--color-text-secondary, #888); }
.step.active .step-label { color: var(--color-primary, #3b82f6); }
.step.completed .step-label { color: var(--color-success, #22c55e); }
.step-connector { width: 2rem; height: 2px; background: var(--color-border, #ddd); margin: 0 0.25rem; }
.step.completed + .step .step-connector { background: var(--color-success, #22c55e); }
</style>
