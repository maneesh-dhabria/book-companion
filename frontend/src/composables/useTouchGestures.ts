import { onUnmounted, ref, type Ref } from 'vue'

export function useTouchGestures(elementRef: Ref<HTMLElement | null>) {
  const isLongPress = ref(false)
  let longPressTimer: ReturnType<typeof setTimeout> | null = null
  const LONG_PRESS_MS = 500

  function onTouchStart(e: TouchEvent) {
    longPressTimer = setTimeout(() => {
      isLongPress.value = true
    }, LONG_PRESS_MS)
  }

  function onTouchEnd() {
    if (longPressTimer) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
    isLongPress.value = false
  }

  function onTouchMove() {
    if (longPressTimer) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
  }

  onUnmounted(() => {
    if (longPressTimer) {
      clearTimeout(longPressTimer)
    }
  })

  return { isLongPress, onTouchStart, onTouchEnd, onTouchMove }
}
