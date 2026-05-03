<script setup lang="ts">
import { computed, ref } from 'vue'

import { audioApi, type AudioInventoryItem } from '@/api/audio'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ bookId: number; file: AudioInventoryItem }>()

const emit = defineEmits<{
  play: [file: AudioInventoryItem]
  removed: [file: AudioInventoryItem]
}>()

const ui = (() => {
  try {
    return useUiStore()
  } catch {
    return null
  }
})()

const confirming = ref(false)
const deleting = ref(false)

const downloadHref = computed(() =>
  audioApi.mp3Url(props.bookId, props.file.content_type, props.file.content_id),
)

const sizeMB = computed(() => (props.file.size_bytes / (1024 * 1024)).toFixed(1))

const minSec = computed(() => {
  const total = Math.floor(props.file.duration_seconds)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
})

function onPlay() {
  emit('play', props.file)
}

function onDeleteClick() {
  confirming.value = true
}

function onCancel() {
  confirming.value = false
}

async function onConfirm() {
  if (deleting.value) return
  deleting.value = true
  try {
    await audioApi.deleteOne(props.bookId, props.file.content_type, props.file.content_id)
    emit('removed', props.file)
    confirming.value = false
  } catch (err) {
    const status = (err as { status?: number }).status
    if (status === 409) {
      ui?.showToast('Wait or cancel the running audio job before deleting.', 'error')
    } else {
      ui?.showToast('Delete failed.', 'error')
    }
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div
    class="bc-audio-row flex items-center gap-3 rounded-md px-3 py-2 ring-1 ring-slate-200 dark:ring-slate-700"
  >
    <div class="flex-1 min-w-0">
      <div class="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
        {{ file.content_type }} #{{ file.content_id }}
      </div>
      <div class="text-xs text-slate-500">
        {{ minSec }} · {{ sizeMB }} MB · {{ file.voice }}
      </div>
    </div>

    <button
      type="button"
      data-testid="play"
      class="rounded-full bg-indigo-600 p-1.5 text-white hover:bg-indigo-500"
      aria-label="Play"
      @click="onPlay"
    >
      ▶
    </button>

    <a
      :href="downloadHref"
      data-testid="download"
      download
      class="rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700"
    >
      Download
    </a>

    <button
      type="button"
      data-testid="delete-row"
      class="rounded-md p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-600"
      aria-label="Delete audio"
      @click="onDeleteClick"
    >
      🗑
    </button>

    <div
      v-if="confirming"
      data-testid="confirm-popover"
      class="ml-2 flex items-center gap-2 rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-700 dark:bg-slate-800"
    >
      <span>Delete this audio file?</span>
      <button
        type="button"
        data-testid="confirm-delete"
        class="rounded bg-red-600 px-2 py-0.5 text-white hover:bg-red-500"
        :disabled="deleting"
        @click="onConfirm"
      >
        Confirm
      </button>
      <button
        type="button"
        data-testid="cancel-delete"
        class="rounded px-2 py-0.5 text-slate-600 hover:bg-slate-200"
        @click="onCancel"
      >
        Cancel
      </button>
    </div>
  </div>
</template>
