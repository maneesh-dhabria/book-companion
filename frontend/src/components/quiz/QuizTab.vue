<template>
  <div data-test="quiz-tab-root" class="quiz-tab">
    <p class="quiz-tab-placeholder">Quiz tab placeholder</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ bookId: number }>()
</script>

<style scoped>
.quiz-tab {
  padding: 1rem;
}
.quiz-tab-placeholder {
  color: var(--color-text-muted, #666);
}
</style>
