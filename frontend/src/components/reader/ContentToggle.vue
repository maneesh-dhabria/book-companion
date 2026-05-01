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
    >
      Original
    </button>
    <button
      class="toggle-btn"
      :class="{ active: mode === 'summary' }"
      @click="$emit('toggle')"
    >
      Summary
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

/* FR-18 / FR-19: inactive tab reads as available, not disabled. */
.toggle-btn:not(.active) {
  color: var(--color-text-secondary);
  cursor: pointer;
  opacity: 1;
}

.toggle-btn:not(.active):hover {
  background: var(--color-bg-tertiary);
}

.toggle-btn.active {
  background: var(--color-accent);
  color: #fff;
}
</style>
