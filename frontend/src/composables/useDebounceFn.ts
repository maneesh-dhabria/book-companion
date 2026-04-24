import { onBeforeUnmount } from 'vue'

export interface DebouncedFn<Args extends unknown[]> {
  (...args: Args): void
  cancel(): void
  flush(): void
}

/**
 * Trailing-edge debounce that auto-cancels on component unmount.
 *
 * Used by LibraryView search (FR-G3.1) and TagChipInput autocomplete.
 */
export function useDebounceFn<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): DebouncedFn<Args> {
  let timer: ReturnType<typeof setTimeout> | null = null
  let pendingArgs: Args | null = null

  const wrapped = ((...args: Args) => {
    pendingArgs = args
    if (timer !== null) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      const current = pendingArgs
      pendingArgs = null
      if (current) fn(...current)
    }, waitMs)
  }) as DebouncedFn<Args>

  wrapped.cancel = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    pendingArgs = null
  }

  wrapped.flush = () => {
    if (timer !== null && pendingArgs) {
      clearTimeout(timer)
      const current = pendingArgs
      timer = null
      pendingArgs = null
      fn(...current)
    }
  }

  onBeforeUnmount(() => wrapped.cancel())
  return wrapped
}
