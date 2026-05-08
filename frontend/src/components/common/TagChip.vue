<template>
  <span
    class="chip tag-chip"
    :class="[toneClass, { removable, suggested, clickable }]"
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

const toneClass = computed(() => {
  if (props.color) return ''
  return props.suggested ? 'chip--warn' : 'chip--neutral'
})

const chipStyle = computed(() =>
  props.color ? { background: props.color } : {},
)
</script>

<style scoped>
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
