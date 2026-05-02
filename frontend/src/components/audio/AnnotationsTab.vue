<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { estimatePlaylistMinutes } from '@/composables/audio/usePlaylistMinutes'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

interface AnnotationLite {
  id: number
  selected_text: string
  note: string | null
}

const props = defineProps<{ bookId: number }>()

const annotations = ref<AnnotationLite[]>([])
const loaded = ref(false)

const ttsPlayer = (() => {
  try {
    return useTtsPlayerStore()
  } catch {
    return null
  }
})()

const highlightCount = computed(() => annotations.value.length)
const noteCount = computed(() => annotations.value.filter((a) => a.note).length)
const minutes = computed(() => estimatePlaylistMinutes(highlightCount.value, noteCount.value))

async function load() {
  try {
    const r = await fetch(`/api/v1/books/${props.bookId}/annotations`)
    if (r.ok) {
      const body = await r.json()
      annotations.value = body.annotations ?? []
    }
  } finally {
    loaded.value = true
  }
}

function onPlayAll() {
  ttsPlayer?.open({ contentType: 'annotations_playlist', contentId: props.bookId })
}

onMounted(load)
</script>

<template>
  <div class="annotations-tab" data-testid="annotations-tab">
    <div v-if="!loaded" class="text-sm text-slate-500">Loading annotations…</div>

    <template v-else-if="highlightCount > 0">
      <div class="flex items-center gap-3">
        <button
          type="button"
          data-testid="play-all-annotations"
          class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500"
          @click="onPlayAll"
        >
          ▶ Play as audio
        </button>
        <span class="text-xs text-slate-500">
          ~{{ minutes }} min · {{ highlightCount }} highlight{{ highlightCount === 1 ? '' : 's' }}
        </span>
      </div>

      <ul class="mt-3 space-y-2">
        <li
          v-for="a in annotations"
          :key="a.id"
          class="rounded-md bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800"
        >
          <p class="text-slate-800 dark:text-slate-200">{{ a.selected_text }}</p>
          <p v-if="a.note" class="mt-1 text-xs text-slate-600 dark:text-slate-400">
            ♪ {{ a.note }}
          </p>
        </li>
      </ul>
    </template>

    <p v-else class="text-sm text-slate-500">No highlights yet.</p>
  </div>
</template>
