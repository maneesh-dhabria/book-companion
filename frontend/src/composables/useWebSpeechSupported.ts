import { ref, type Ref } from 'vue'

/**
 * FR-17 / plan T6: cached one-shot probe for `window.speechSynthesis`.
 *
 * Browser support doesn't change in-session, so we probe once on first
 * call and cache the result. Module-level singleton — not a Pinia store
 * (no UI binding state lives here).
 */
let supported: Ref<boolean> | null = null

export function useWebSpeechSupported(): { supported: Readonly<Ref<boolean>> } {
  if (supported === null) {
    supported = ref(typeof window !== 'undefined' && 'speechSynthesis' in window)
  }
  return { supported }
}

/** Test-only: clears the singleton cache so subsequent calls re-probe. */
export function _resetForTests(): void {
  supported = null
}
