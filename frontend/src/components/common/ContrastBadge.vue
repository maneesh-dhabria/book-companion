<template>
  <span class="contrast-badge" :class="gradeClass" :title="titleText">
    {{ ratio }}:1
    <span class="grade">{{ grade }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { contrastGrade, contrastRatio } from '@/utils/contrast'

const props = defineProps<{ fg: string; bg: string }>()

const ratio = computed(() => {
  try {
    return contrastRatio(props.fg, props.bg)
  } catch {
    return 1
  }
})
const grade = computed(() => contrastGrade(ratio.value))
const gradeClass = computed(() => `grade-${grade.value.toLowerCase()}`)
const titleText = computed(
  () => `Contrast ratio ${ratio.value}:1 — WCAG ${grade.value}`,
)
</script>

<style scoped>
.contrast-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 0.5rem;
  background: rgba(0, 0, 0, 0.06);
}
.grade {
  font-weight: 600;
  letter-spacing: 0.03em;
}
.grade-aaa {
  color: #14532d;
}
.grade-aa {
  color: #166534;
}
.grade-aa-large {
  color: #854d0e;
}
.grade-fail {
  color: #b91c1c;
}
</style>
