import { onMounted, onUnmounted } from 'vue'

interface KeyboardShortcut {
  key: string
  meta?: boolean
  ctrl?: boolean
  shift?: boolean
  handler: (e: KeyboardEvent) => void
}

export function useKeyboard(shortcuts: KeyboardShortcut[]) {
  function handleKeyDown(e: KeyboardEvent) {
    for (const shortcut of shortcuts) {
      const metaMatch = shortcut.meta ? e.metaKey : !e.metaKey || shortcut.meta === undefined
      const ctrlMatch = shortcut.ctrl ? e.ctrlKey : !e.ctrlKey || shortcut.ctrl === undefined
      const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey || shortcut.shift === undefined

      if (
        e.key.toLowerCase() === shortcut.key.toLowerCase() &&
        (shortcut.meta ? e.metaKey : true) &&
        (shortcut.ctrl ? e.ctrlKey : true) &&
        (shortcut.shift ? e.shiftKey : true)
      ) {
        e.preventDefault()
        shortcut.handler(e)
        return
      }
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown)
  })
}
