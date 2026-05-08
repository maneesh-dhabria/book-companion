<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    totalSentences: number
    currentIndex: number
  }>(),
  { totalSentences: 0, currentIndex: 0 },
)

interface Segment {
  state: 'done' | 'current' | 'upcoming'
}

const segments = computed<Segment[]>(() => {
  const total = Math.max(0, Math.floor(props.totalSentences))
  const cur = Math.max(0, Math.min(Math.floor(props.currentIndex), total - 1))
  const out: Segment[] = []
  for (let i = 0; i < total; i++) {
    if (i < cur) out.push({ state: 'done' })
    else if (i === cur) out.push({ state: 'current' })
    else out.push({ state: 'upcoming' })
  }
  return out
})
</script>

<template>
  <div
    v-if="segments.length > 0"
    data-testid="sentence-progress-bar"
    role="progressbar"
    :aria-valuemin="0"
    :aria-valuemax="totalSentences"
    :aria-valuenow="currentIndex"
    aria-label="Sentence progress"
    class="sentence-progress"
  >
    <span
      v-for="(seg, i) in segments"
      :key="i"
      data-segment
      :data-state="seg.state"
      class="seg"
      :class="{
        'seg--done': seg.state === 'done',
        'seg--current': seg.state === 'current',
        'seg--upcoming': seg.state === 'upcoming',
      }"
    />
  </div>
</template>

<style scoped>
.sentence-progress {
  display: flex;
  gap: 1px;
  height: 4px;
  width: 100%;
  margin-bottom: 4px;
}
.seg {
  flex: 1;
  min-width: 2px;
  border-radius: 1px;
}
.seg--done {
  background: rgb(99 102 241);
}
.seg--current {
  background: transparent;
  border: 1px solid rgb(99 102 241);
}
.seg--upcoming {
  background: rgb(226 232 240);
}
.dark .seg--done {
  background: rgb(129 140 248);
}
.dark .seg--current {
  border-color: rgb(129 140 248);
}
.dark .seg--upcoming {
  background: rgb(51 65 85);
}
</style>
