<template>
  <div v-if="visible" data-test="session-tally" class="session-tally">
    <span class="line">
      Session: {{ sessionTally.got_it }} / {{ sessionTally.partial }} / {{ sessionTally.missed }}
      <span v-if="sessionSkipped > 0" class="skip">({{ sessionSkipped }} skipped)</span>
    </span>
    <span class="sep">·</span>
    <span class="line">
      Lifetime: {{ lifetime.got_it }} / {{ lifetime.partial }} / {{ lifetime.missed }}
      across {{ lifetime.session_count }} {{ lifetime.session_count === 1 ? 'session' : 'sessions' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QuizLifetimeTally, QuizSessionTally } from '@/types'

const props = defineProps<{
  sessionTally: QuizSessionTally
  lifetime: QuizLifetimeTally
  sessionSkipped: number
}>()

// E24: hide the tally when there are no completed sessions OR no in-flight session
// activity to surface — caller passes a zeroed sessionTally + zero session_count.
const visible = computed(() => {
  const session = props.sessionTally
  const hasSessionActivity =
    session.got_it + session.partial + session.missed + props.sessionSkipped > 0
  return hasSessionActivity || props.lifetime.session_count > 0
})
</script>

<style scoped>
.session-tally {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.85rem;
  background: #eef2ff;
  color: #3730a3;
  border-bottom: 1px solid #c7d2fe;
  font-size: 0.85rem;
  font-weight: 500;
}
.skip {
  margin-left: 0.3rem;
  color: #6b7280;
  font-weight: 400;
}
.sep {
  color: #9ca3af;
}
</style>
