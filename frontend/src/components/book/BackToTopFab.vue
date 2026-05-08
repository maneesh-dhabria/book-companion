<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const visible = ref(false)

function onScroll() {
  visible.value = window.scrollY > window.innerHeight
}

function backToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <button
    v-if="visible"
    type="button"
    class="back-to-top chip chip--accent"
    aria-label="Back to top"
    title="Back to top"
    @click="backToTop"
  >
    ↑ Top
  </button>
</template>

<style scoped>
.back-to-top {
  position: fixed;
  right: 1.5rem;
  bottom: calc(var(--playbar-height, 0px) + 1.5rem);
  z-index: 30;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.5rem 0.9rem;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
}

.back-to-top:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: 2px;
}
</style>
