<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { AudioContentType } from '@/api/audio'
import { audioPositionApi, getBrowserId, type AudioPosition } from '@/api/audioPosition'
import { useAudioApiError } from '@/composables/audio/useAudioApiError'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const props = defineProps<{
  contentType: AudioContentType
  contentId: number
  audioStatus: 'complete' | 'partial' | 'none'
  totalSentences: number
}>()

const position = ref<AudioPosition | null>(null)
const loaded = ref(false)
const onErr = useAudioApiError()
const store = useTtsPlayerStore()

onMounted(async () => {
  if (props.audioStatus !== 'complete') {
    loaded.value = true
    return
  }
  try {
    position.value = await audioPositionApi.get({
      content_type: props.contentType,
      content_id: props.contentId,
      browser_id: getBrowserId(),
    })
  } catch (e) {
    onErr(e as { status?: number })
  } finally {
    loaded.value = true
  }
})

function resume() {
  if (!position.value) return
  store.open({
    contentType: props.contentType,
    contentId: props.contentId,
    sentenceIndex: position.value.sentence_index,
  })
}

function startFromBeginning() {
  store.open({
    contentType: props.contentType,
    contentId: props.contentId,
    sentenceIndex: 0,
  })
}
</script>

<template>
  <div
    v-if="loaded && position"
    class="bc-resume rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900 dark:bg-indigo-900/30 dark:text-indigo-100"
  >
    <p>
      Resume from sentence {{ position.sentence_index + 1 }} of {{ totalSentences }}
    </p>
    <p
      v-if="position.has_other_browser"
      class="mt-1 text-xs text-indigo-700 dark:text-indigo-300"
    >
      You last listened on a different browser
      <span v-if="position.other_browser_updated_at">
        ({{ new Date(position.other_browser_updated_at).toLocaleString() }})
      </span>
    </p>
    <div class="mt-2 flex gap-2">
      <button
        type="button"
        data-testid="resume"
        class="rounded-md bg-indigo-600 px-3 py-1 text-white hover:bg-indigo-500"
        @click="resume"
      >
        Resume
      </button>
      <button
        type="button"
        data-testid="start-from-beginning"
        class="rounded-md border border-indigo-300 bg-white px-3 py-1 text-indigo-700 hover:bg-indigo-50"
        @click="startFromBeginning"
      >
        Start from beginning
      </button>
    </div>
  </div>
</template>
