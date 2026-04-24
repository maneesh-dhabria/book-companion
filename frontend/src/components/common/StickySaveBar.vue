<template>
  <div class="sticky-save-bar" role="toolbar" :aria-hidden="!dirty">
    <div class="label">
      <slot name="label">Unsaved changes</slot>
    </div>
    <div class="actions">
      <button
        v-if="canRevert"
        type="button"
        class="revert"
        :disabled="!dirty"
        @click="$emit('revert')"
      >
        Revert
      </button>
      <button
        type="button"
        class="save"
        :disabled="!dirty"
        @click="$emit('save')"
      >
        <slot name="save-label">Save &amp; apply</slot>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ dirty: boolean; canRevert?: boolean }>()
defineEmits<{ (e: 'save'): void; (e: 'revert'): void }>()
</script>

<style scoped>
.sticky-save-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid #e5e7eb;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.05);
  transition: opacity 0.15s ease, transform 0.2s ease;
}
.sticky-save-bar[aria-hidden='true'] {
  opacity: 0.6;
}
.label {
  font-size: 0.8125rem;
  color: #475569;
}
.actions {
  display: flex;
  gap: 0.35rem;
}
button {
  border: 0;
  border-radius: 0.25rem;
  padding: 0.4rem 0.9rem;
  font-size: 0.8125rem;
  cursor: pointer;
}
.revert {
  background: #f1f5f9;
  color: #475569;
}
.save {
  background: #4f46e5;
  color: white;
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
