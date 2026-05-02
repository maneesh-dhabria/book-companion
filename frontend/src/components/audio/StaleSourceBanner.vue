<script setup lang="ts">
import { computed, ref } from 'vue'

import type { AudioContentType } from '@/api/audio'
import { audioApi } from '@/api/audio'
import { useAudioApiError } from '@/composables/audio/useAudioApiError'

import type { StaleReason } from '@/stores/ttsPlayer'

const props = defineProps<{
  staleReason: StaleReason
  bookId: number
  contentType: AudioContentType
  contentId: number
  voice?: string
}>()

const emit = defineEmits<{ regenerated: [jobId: number] }>()

const inFlight = ref(false)
const onErr = useAudioApiError()

const copy = computed(() => {
  switch (props.staleReason) {
    case 'source_changed':
      return 'Source updated since audio generated — regenerate to hear the latest version.'
    case 'sanitizer_upgraded':
      return 'Audio engine updated — regenerate for improved fidelity.'
    case 'segmenter_drift':
      return 'Sentence boundaries shifted — regenerate to keep highlights aligned.'
    default:
      return 'Audio is stale.'
  }
})

async function regenerate() {
  if (inFlight.value) return
  inFlight.value = true
  try {
    const scope =
      props.contentType === 'book_summary' ? 'book' : 'sections'
    const body = {
      scope: scope as 'book' | 'sections',
      voice: props.voice ?? 'af_sarah',
      engine: 'kokoro' as const,
      ...(scope === 'sections' ? { section_ids: [props.contentId] } : {}),
    }
    const res = await audioApi.start(props.bookId, body)
    emit('regenerated', res.job_id)
  } catch (e) {
    onErr(e as { status?: number })
  } finally {
    inFlight.value = false
  }
}
</script>

<template>
  <div
    class="bc-banner rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-100"
    role="status"
  >
    <p>{{ copy }}</p>
    <button
      type="button"
      data-testid="regenerate"
      class="mt-2 rounded-md bg-amber-600 px-3 py-1 text-white hover:bg-amber-500 disabled:opacity-50"
      :disabled="inFlight"
      @click="regenerate"
    >
      {{ inFlight ? 'Queuing…' : 'Regenerate' }}
    </button>
  </div>
</template>
