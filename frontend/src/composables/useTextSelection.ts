import { onMounted, onUnmounted, reactive, ref } from 'vue'

export interface TextSelectionState {
  text: string
  startOffset: number
  endOffset: number
  rect: { top: number; left: number; width: number; height: number } | null
}

export function useTextSelection(containerRef: { value: HTMLElement | null }) {
  const selection = reactive<TextSelectionState>({
    text: '',
    startOffset: 0,
    endOffset: 0,
    rect: null,
  })
  const isSelecting = ref(false)

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function handleSelectionChange() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      const sel = document.getSelection()
      if (!sel || sel.isCollapsed || !sel.rangeCount) {
        clear()
        return
      }

      const range = sel.getRangeAt(0)
      const container = containerRef.value
      if (!container || !container.contains(range.commonAncestorContainer)) {
        clear()
        return
      }

      const text = sel.toString().trim()
      if (!text) {
        clear()
        return
      }

      const rect = range.getBoundingClientRect()
      selection.text = text
      selection.startOffset = range.startOffset
      selection.endOffset = range.endOffset
      selection.rect = {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      }
      isSelecting.value = true
    }, 150)
  }

  function clear() {
    selection.text = ''
    selection.startOffset = 0
    selection.endOffset = 0
    selection.rect = null
    isSelecting.value = false
  }

  onMounted(() => {
    document.addEventListener('selectionchange', handleSelectionChange)
  })

  onUnmounted(() => {
    document.removeEventListener('selectionchange', handleSelectionChange)
    if (debounceTimer) clearTimeout(debounceTimer)
  })

  return {
    selection,
    isSelecting,
    clear,
  }
}
