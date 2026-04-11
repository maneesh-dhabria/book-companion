<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title?: string
}>(), {
  title: '',
})

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

// Snap points as percentage of viewport height
const SNAP_PEEK = 0.3
const SNAP_HALF = 0.5
const SNAP_FULL = 0.9

const currentSnap = ref(SNAP_PEEK)
const dragging = ref(false)
const startY = ref(0)
const startTranslate = ref(0)
const translateY = ref(0)

const sheetStyle = computed(() => {
  if (dragging.value) {
    return { transform: `translateY(${translateY.value}px)` }
  }
  const height = currentSnap.value * 100
  return { transform: `translateY(${100 - height}%)` }
})

const contentScrollable = computed(() => currentSnap.value === SNAP_FULL)

function close() {
  emit('update:open', false)
  currentSnap.value = SNAP_PEEK
}

function onTouchStart(e: TouchEvent) {
  dragging.value = true
  startY.value = e.touches[0].clientY
  const vh = window.innerHeight
  startTranslate.value = vh * (1 - currentSnap.value)
  translateY.value = startTranslate.value
}

function onTouchMove(e: TouchEvent) {
  if (!dragging.value) return
  const deltaY = e.touches[0].clientY - startY.value
  translateY.value = Math.max(0, startTranslate.value + deltaY)
}

function onTouchEnd() {
  if (!dragging.value) return
  dragging.value = false

  const vh = window.innerHeight
  const currentPercent = 1 - translateY.value / vh

  // Snap to nearest point, or dismiss if dragged below peek
  if (currentPercent < SNAP_PEEK * 0.5) {
    close()
  } else if (currentPercent < (SNAP_PEEK + SNAP_HALF) / 2) {
    currentSnap.value = SNAP_PEEK
  } else if (currentPercent < (SNAP_HALF + SNAP_FULL) / 2) {
    currentSnap.value = SNAP_HALF
  } else {
    currentSnap.value = SNAP_FULL
  }
}

function onBackdropClick() {
  close()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open) {
    close()
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    currentSnap.value = SNAP_PEEK
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('keydown', onKeydown)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div
        v-if="open"
        class="bottom-sheet-overlay"
        data-testid="bottom-sheet"
        role="dialog"
        aria-modal="true"
        :aria-label="title || 'Bottom sheet'"
      >
        <div class="bottom-sheet-backdrop" @click="onBackdropClick" />
        <div
          class="bottom-sheet-container"
          :style="sheetStyle"
          :class="{ dragging, scrollable: contentScrollable }"
        >
          <div
            class="bottom-sheet-handle"
            @touchstart.passive="onTouchStart"
            @touchmove.passive="onTouchMove"
            @touchend="onTouchEnd"
          >
            <div class="handle-pill" />
          </div>
          <div v-if="title" class="bottom-sheet-header">
            <h3 class="bottom-sheet-title">{{ title }}</h3>
          </div>
          <div class="bottom-sheet-content" :class="{ scrollable: contentScrollable }">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.bottom-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.bottom-sheet-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  transition: opacity 0.3s;
}

.bottom-sheet-container {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 90vh;
  background: var(--color-bg-primary, white);
  border-radius: 1rem 1rem 0 0;
  transition: transform 0.3s ease-out;
  display: flex;
  flex-direction: column;
}

.bottom-sheet-container.dragging {
  transition: none;
}

.bottom-sheet-handle {
  display: flex;
  justify-content: center;
  padding: 0.75rem 0;
  cursor: grab;
  touch-action: none;
  min-height: 44px;
  align-items: center;
}

.handle-pill {
  width: 2rem;
  height: 0.25rem;
  background: var(--color-border, #d1d5db);
  border-radius: 0.125rem;
}

.bottom-sheet-header {
  padding: 0 1rem 0.75rem;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.bottom-sheet-title {
  font-size: 1rem;
  font-weight: 600;
}

.bottom-sheet-content {
  flex: 1;
  overflow: hidden;
  padding: 1rem;
}

.bottom-sheet-content.scrollable {
  overflow-y: auto;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.3s;
}

.sheet-enter-active .bottom-sheet-container,
.sheet-leave-active .bottom-sheet-container {
  transition: transform 0.3s ease-out;
}

.sheet-enter-from .bottom-sheet-backdrop,
.sheet-leave-to .bottom-sheet-backdrop {
  opacity: 0;
}

.sheet-enter-from .bottom-sheet-container,
.sheet-leave-to .bottom-sheet-container {
  transform: translateY(100%) !important;
}
</style>
