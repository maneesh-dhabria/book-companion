<template>
  <span
    class="tag-chip"
    :class="{ removable, suggested, clickable }"
    :style="chipStyle"
    @click="$emit('click')"
  >
    <slot name="prefix" />
    <span class="name">{{ label }}</span>
    <button
      v-if="removable"
      type="button"
      class="remove"
      :aria-label="`Remove ${label}`"
      @click.stop="$emit('remove')"
    >
      &times;
    </button>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  color?: string | null
  removable?: boolean
  suggested?: boolean
  clickable?: boolean
}>()

defineEmits<{
  (e: 'remove'): void
  (e: 'click'): void
}>()

const chipStyle = computed(() =>
  props.color
    ? { '--chip-color': props.color }
    : {},
)
</script>

<style scoped>
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.125rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  line-height: 1.4;
  background: var(--chip-color, rgba(99, 102, 241, 0.12));
  color: #1e293b;
  border: 1px solid rgba(0, 0, 0, 0.08);
  white-space: nowrap;
}
.tag-chip.suggested {
  background: rgba(234, 179, 8, 0.18);
  border-color: rgba(234, 179, 8, 0.35);
}
.tag-chip.clickable {
  cursor: pointer;
  transition: filter 0.12s ease;
}
.tag-chip.clickable:hover {
  filter: brightness(0.95);
}
.remove {
  background: transparent;
  border: 0;
  padding: 0 0.2rem;
  font-size: 0.9rem;
  line-height: 1;
  cursor: pointer;
  color: inherit;
}
.remove:hover {
  color: #b91c1c;
}
</style>
