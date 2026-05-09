<template>
  <div data-test="already-asked-wrapper" class="already-asked">
    <a
      data-test="already-asked"
      class="link"
      href="#"
      @click.prevent="onClick"
      @mouseenter="onHover"
      @mouseleave="hovered = false"
      @focus="onHover"
      @blur="hovered = false"
    >
      Already asked
    </a>
    <span
      v-if="hovered && !tooltipSeen"
      data-test="already-asked-tooltip"
      class="tooltip"
      role="tooltip"
    >
      {{ COPY.alreadyAskedTooltip }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { discardQuestion } from '@/api/quizSessions'
import { COPY } from '@/components/quiz/copy'
import type { QuizDiscardResponse } from '@/types'

const props = defineProps<{ sessionId: number; questionId: number }>()
const emit = defineEmits<{
  (e: 'discarded', resp: QuizDiscardResponse): void
  (e: 'error', err: unknown): void
}>()

const TOOLTIP_KEY = 'quiz.alreadyAsked.tooltipSeen'
const hovered = ref(false)
const tooltipSeen = ref<boolean>(sessionStorage.getItem(TOOLTIP_KEY) === '1')
const busy = ref(false)

function onHover() {
  if (tooltipSeen.value) return
  hovered.value = true
}

async function onClick() {
  if (busy.value) return
  // Mark tooltip as seen on first interaction so future hovers stay quiet.
  if (!tooltipSeen.value) {
    sessionStorage.setItem(TOOLTIP_KEY, '1')
    tooltipSeen.value = true
  }
  busy.value = true
  try {
    const resp = await discardQuestion(props.sessionId, props.questionId)
    emit('discarded', resp)
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
    hovered.value = false
  }
}
</script>

<style scoped>
.already-asked {
  position: relative;
  display: inline-block;
}
.link {
  font-size: 0.85rem;
  color: #4f46e5;
  text-decoration: underline;
  cursor: pointer;
}
.link:hover {
  color: #3730a3;
}
.tooltip {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.4rem;
  padding: 0.4rem 0.6rem;
  background: #111827;
  color: #f9fafb;
  font-size: 0.78rem;
  border-radius: 4px;
  white-space: normal;
  width: max-content;
  max-width: 18rem;
  z-index: 50;
}
</style>
