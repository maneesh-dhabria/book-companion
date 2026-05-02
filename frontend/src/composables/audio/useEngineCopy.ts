export type EngineReason =
  | 'no_pregen'
  | 'model_not_downloaded'
  | 'model_loading'
  | 'engine_unavailable'
  | 'pregenerated'
  | 'fallback_no_pregen'
  | 'user_setting'
  | 'kokoro_unavailable'

export function useEngineCopy(reason: EngineReason | null | undefined, defaultEngine: string | null): string {
  const def = defaultEngine ?? 'kokoro'
  switch (reason) {
    case 'no_pregen':
    case 'fallback_no_pregen':
      return `Default is ${def}; using web-speech for this section because no pre-generated audio exists`
    case 'model_not_downloaded':
      return `Default is ${def}; model is not downloaded yet — using web-speech instead`
    case 'model_loading':
      return `Default is ${def}; model is still loading — using web-speech temporarily`
    case 'engine_unavailable':
    case 'kokoro_unavailable':
      return `Default engine is unavailable; using web-speech as fallback`
    case 'pregenerated':
      return `Playing pre-generated ${def} audio`
    case 'user_setting':
      return `Active engine matches your setting`
    default:
      return ''
  }
}
