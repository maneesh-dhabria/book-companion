<template>
  <span class="contrast-badge chip chip--neutral" :class="gradeClass" :title="titleText">
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
  gap: 0.35rem;
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
