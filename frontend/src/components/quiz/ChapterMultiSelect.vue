<template>
  <ul data-test="chapter-multi-select" class="chapter-multi-select">
    <li v-for="s in eligibleSections" :key="s.id" class="row">
      <label>
        <input
          type="checkbox"
          :data-test="'chapter-cb-' + s.id"
          :value="s.id"
          :checked="selectedIds.includes(s.id)"
          @change="toggle(s)"
        />
        <span class="title">{{ s.title }}</span>
        <span class="tokens">{{ tokensFor(s).toLocaleString() }} tokens</span>
      </label>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SectionBrief } from '@/types'

const props = defineProps<{
  sections: SectionBrief[]
  selectedIds: number[]
  budgetMax: number
  budgetUsed: number
}>()

const emit = defineEmits<{ toggle: [sectionId: number] }>()

const ELIGIBLE_TYPES = new Set(['chapter', 'part', 'section'])

const eligibleSections = computed(() =>
  props.sections.filter((s) => ELIGIBLE_TYPES.has(s.section_type)),
)

function tokensFor(s: SectionBrief): number {
  // Rough: backend's token_estimate or fallback to char_count/4.
  return s.content_token_count ?? Math.ceil((s.content_char_count ?? 0) / 4)
}

function toggle(s: SectionBrief): void {
  emit('toggle', s.id)
}
</script>

<style scoped>
.chapter-multi-select {
  list-style: none;
  padding: 0;
  margin: 0;
}
.chapter-multi-select .row {
  padding: 0.25rem 0;
  border-bottom: 1px solid var(--color-border-subtle, #eee);
}
.chapter-multi-select label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.chapter-multi-select .title {
  flex: 1;
}
.chapter-multi-select .tokens {
  color: var(--color-text-muted, #666);
  font-variant-numeric: tabular-nums;
}
</style>
