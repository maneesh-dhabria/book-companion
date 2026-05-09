<template>
  <div data-test="past-qa-panel" class="past-qa-panel">
    <h3>Past Q&amp;A</h3>
    <p>{{ sessions.length }} prior session(s).</p>
  </div>
</template>

<script setup lang="ts">
import type { QuizSessionListItem } from '@/types'

defineProps<{ sessions: QuizSessionListItem[] }>()
</script>
