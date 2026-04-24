<template>
  <div class="suggested-bar">
    <span class="headline">Suggested tags:</span>
    <TagChip
      v-for="name in suggestions"
      :key="name"
      :label="name"
      suggested
      clickable
      @click="$emit('accept', name)"
    >
      <template #prefix>
        <span class="sparkle" aria-hidden="true">✨</span>
      </template>
    </TagChip>
    <button
      v-if="suggestions.length"
      type="button"
      class="dismiss-all"
      @click="dismissAll"
    >
      Dismiss all
    </button>
  </div>
</template>

<script setup lang="ts">
import TagChip from '@/components/common/TagChip.vue'

const props = defineProps<{ suggestions: string[] }>()
const emit = defineEmits<{
  (e: 'accept', name: string): void
  (e: 'reject', name: string): void
}>()

function dismissAll() {
  for (const n of props.suggestions) emit('reject', n)
}
</script>

<style scoped>
.suggested-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: rgba(234, 179, 8, 0.07);
  border: 1px dashed rgba(234, 179, 8, 0.35);
  border-radius: 0.375rem;
}
.headline {
  font-size: 0.8125rem;
  color: #92400e;
  font-weight: 600;
}
.sparkle {
  font-size: 0.75rem;
}
.dismiss-all {
  margin-left: auto;
  background: transparent;
  border: 0;
  color: #854d0e;
  cursor: pointer;
  font-size: 0.75rem;
  text-decoration: underline;
}
</style>
