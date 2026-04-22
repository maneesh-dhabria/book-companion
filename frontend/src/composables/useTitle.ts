import { type MaybeRefOrGetter, toValue, watchEffect } from 'vue'

const APP_NAME = 'Book Companion'

/**
 * Keep ``document.title`` in sync with a reactive value. Passing a plain
 * string applies it once; passing a ref or getter reacts to changes. All
 * titles are suffixed with " — Book Companion" unless the value itself
 * is the bare app name.
 */
export function useTitle(source: MaybeRefOrGetter<string | null | undefined>) {
  watchEffect(() => {
    const value = toValue(source)
    if (value == null || value === '') {
      document.title = APP_NAME
      return
    }
    if (value === APP_NAME) {
      document.title = APP_NAME
      return
    }
    document.title = `${value} — ${APP_NAME}`
  })
}

export const APP_TITLE = APP_NAME
