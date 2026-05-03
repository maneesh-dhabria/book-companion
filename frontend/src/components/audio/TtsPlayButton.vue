<script setup lang="ts">
import { computed } from 'vue'

import type { AudioContentType } from '@/api/audio'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const props = defineProps<{
  contentType: AudioContentType
  contentId: number
  hasSummary?: boolean
  bookId?: number
}>()

const store = useTtsPlayerStore()

const disabled = computed(() => props.hasSummary === false)

function onClick() {
  if (disabled.value) return
  store.open({
    contentType: props.contentType,
    contentId: props.contentId,
  })
}
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
    :disabled="disabled || undefined"
    :aria-disabled="disabled ? 'true' : undefined"
    :title="disabled ? 'Audio is only generated for summaries' : 'Listen'"
    @click="onClick"
  >
    <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path d="M6 4l10 6-10 6V4z" />
    </svg>
    <span>Listen</span>
  </button>
</template>
