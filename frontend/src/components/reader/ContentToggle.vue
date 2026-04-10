<script setup lang="ts">
defineProps<{
  mode: 'original' | 'summary'
  hasSummary: boolean
}>()

defineEmits<{
  toggle: []
}>()
</script>

<template>
  <div class="content-toggle">
    <button
      class="toggle-btn"
      :class="{ active: mode === 'original' }"
      @click="$emit('toggle')"
      :disabled="mode === 'original'"
    >
      Original
    </button>
    <button
      class="toggle-btn"
      :class="{ active: mode === 'summary' }"
      @click="$emit('toggle')"
      :disabled="mode === 'summary' || !hasSummary"
    >
      {{ hasSummary ? 'Summary' : 'No Summary' }}
    </button>
  </div>
</template>

<style scoped>
.content-toggle {
  display: flex;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

.toggle-btn {
  padding: 4px 12px;
  border: none;
  background: var(--color-bg-primary);
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.1s;
}

.toggle-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.toggle-btn.active {
  background: var(--color-accent);
  color: #fff;
}
</style>
