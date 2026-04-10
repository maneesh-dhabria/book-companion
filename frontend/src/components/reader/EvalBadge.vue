<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  passed: number
  total: number
}>()

const color = computed(() => {
  if (props.total === 0) return 'gray'
  const ratio = props.passed / props.total
  if (ratio >= 1) return 'green'
  if (ratio >= 0.75) return 'yellow'
  return 'red'
})
</script>

<template>
  <span class="eval-badge" :class="color">
    {{ passed }}/{{ total }}
  </span>
</template>

<style scoped>
.eval-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.eval-badge.green { background: #dcfce7; color: #166534; }
.eval-badge.yellow { background: #fef3c7; color: #92400e; }
.eval-badge.red { background: #fee2e2; color: #991b1b; }
.eval-badge.gray { background: var(--color-bg-tertiary); color: var(--color-text-muted); }
</style>
