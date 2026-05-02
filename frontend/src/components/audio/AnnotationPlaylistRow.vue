<script setup lang="ts">
interface AnnotationLite {
  id: number
  selected_text: string
  note: string | null
}

const props = defineProps<{
  annotation: AnnotationLite
  index: number
  isActive?: boolean
}>()

const emit = defineEmits<{ 'jump-to': [index: number] }>()

function onClick() {
  emit('jump-to', props.index)
}
</script>

<template>
  <div
    class="bc-annotation-row cursor-pointer rounded-md px-3 py-2 ring-1 ring-slate-200 dark:ring-slate-700"
    :class="{ 'bc-sentence-active': isActive }"
    role="button"
    tabindex="0"
    @click="onClick"
    @keydown.enter="onClick"
  >
    <p class="text-sm text-slate-800 dark:text-slate-200">{{ annotation.selected_text }}</p>
    <div
      v-if="annotation.note"
      data-testid="audible-cue"
      class="mt-1 flex items-center gap-2 text-xs text-slate-500"
    >
      <span aria-hidden="true">♪</span>
      <span>{{ annotation.note }}</span>
    </div>
  </div>
</template>
