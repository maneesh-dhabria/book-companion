<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const popoverRef = ref<HTMLElement | null>(null)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

function onClickOutside(e: MouseEvent) {
  const el = popoverRef.value
  if (!el) return
  if (e.target instanceof Node && !el.contains(e.target)) {
    emit('close')
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      await nextTick()
      popoverRef.value?.focus()
      document.addEventListener('keydown', onKeydown)
      // Defer the click listener so the click that opened the popover
      // doesn't immediately close it.
      setTimeout(() => document.addEventListener('click', onClickOutside), 0)
    } else {
      document.removeEventListener('keydown', onKeydown)
      document.removeEventListener('click', onClickOutside)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <div
    v-if="open"
    ref="popoverRef"
    data-testid="difference-popover"
    role="dialog"
    aria-modal="false"
    aria-label="What's the difference between engines?"
    tabindex="-1"
    class="diff-popover"
  >
    <h3 class="diff-popover__title">Kokoro vs. Web Speech</h3>
    <p class="diff-popover__copy">
      <strong>Kokoro</strong> generates audio files on disk. You get full
      seek/scrub controls, a precise timestamp, and persistent resume across
      devices. Generation takes a few minutes per book.
    </p>
    <p class="diff-popover__copy">
      <strong>Web Speech</strong> uses your browser's voice. Playback is
      instant, but you can't seek/scrub mid-sentence and there's no precise
      timestamp.
    </p>
    <div class="diff-popover__actions">
      <router-link to="/settings/tts#audio" class="btn-primary">
        Open audio settings →
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.diff-popover {
  position: absolute;
  z-index: 50;
  margin-top: 0.5rem;
  max-width: 22rem;
  background: rgb(255 255 255);
  color: rgb(15 23 42);
  border: 1px solid rgb(226 232 240);
  border-radius: 0.5rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 1rem;
  outline: none;
}
.dark .diff-popover {
  background: rgb(30 41 59);
  color: rgb(241 245 249);
  border-color: rgb(51 65 85);
}
.diff-popover__title {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
}
.diff-popover__copy {
  font-size: 0.8125rem;
  line-height: 1.4;
  margin: 0 0 0.625rem 0;
}
.diff-popover__actions {
  margin-top: 0.5rem;
}
</style>
