import { useUiStore } from '@/stores/ui'

export interface ToastLike {
  kind: 'warning' | 'error' | 'info'
  text: string
  action?: 'Retry'
}

export type ToastEmit = (toast: ToastLike) => void

interface ApiLikeError {
  status?: number
  message?: string
  code?: string
}

function classify(error: ApiLikeError): ToastLike {
  const status = error?.status ?? 0
  if (status === 0 || error?.code === 'NETWORK') {
    return {
      kind: 'warning',
      text: 'Reconnecting to the server…',
      action: 'Retry',
    }
  }
  if (status === 503) {
    return {
      kind: 'warning',
      text: 'Audio generation is temporarily unavailable. Try again in a moment.',
      action: 'Retry',
    }
  }
  if (status === 429) {
    return {
      kind: 'warning',
      text: 'Rate limit reached — please wait a minute before retrying.',
    }
  }
  if (status === 409) {
    return {
      kind: 'info',
      text: 'An audio job is already in progress for this book.',
    }
  }
  if (status >= 500) {
    return {
      kind: 'error',
      text: 'Audio request failed. Please try again.',
      action: 'Retry',
    }
  }
  return {
    kind: 'error',
    text: error?.message ?? 'Audio request failed.',
  }
}

export function useAudioApiError(emit?: ToastEmit) {
  return (error: ApiLikeError): ToastLike => {
    const toast = classify(error)
    if (emit) {
      emit(toast)
    } else {
      const ui = useUiStore()
      ui.showToast(
        toast.text,
        toast.kind === 'warning' ? 'warning' : toast.kind === 'info' ? 'info' : 'error',
      )
    }
    return toast
  }
}
