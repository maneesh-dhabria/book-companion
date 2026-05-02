<script setup lang="ts">
export type SectionAudioStatus = 'none' | 'ready' | 'stale' | 'generating'

const props = withDefaults(
  defineProps<{
    bookId: number
    sectionId: number
    sectionTitle: string
    audioStatus: SectionAudioStatus
    selectable?: boolean
    selected?: boolean
  }>(),
  { selectable: false, selected: false },
)

const emit = defineEmits<{
  play: [sectionId: number]
  regenerate: [sectionId: number]
  delete: [sectionId: number]
  'select-toggle': [sectionId: number, value: boolean]
}>()

const STATUS_LABEL: Record<SectionAudioStatus, string> = {
  none: 'No audio',
  ready: 'Ready',
  stale: 'Stale',
  generating: 'Generating…',
}

function onPlay() {
  emit('play', props.sectionId)
}
function onRegenerate() {
  emit('regenerate', props.sectionId)
}
function onDelete() {
  emit('delete', props.sectionId)
}
function onToggle(e: Event) {
  emit('select-toggle', props.sectionId, (e.target as HTMLInputElement).checked)
}
</script>

<template>
  <div
    class="bc-sections-audio-row flex items-center gap-3 rounded-md px-3 py-2 ring-1 ring-slate-200 dark:ring-slate-700"
  >
    <input
      v-if="selectable"
      type="checkbox"
      data-testid="bulk-select"
      :checked="selected"
      @change="onToggle"
    />
    <div class="flex-1 min-w-0">
      <div class="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
        {{ sectionTitle }}
      </div>
    </div>

    <span
      :data-testid="`audio-status-${audioStatus}`"
      class="rounded-full px-2 py-0.5 text-xs"
      :class="{
        'bg-slate-100 text-slate-600': audioStatus === 'none',
        'bg-emerald-100 text-emerald-800': audioStatus === 'ready',
        'bg-amber-100 text-amber-800': audioStatus === 'stale',
        'bg-indigo-100 text-indigo-800': audioStatus === 'generating',
      }"
    >
      {{ STATUS_LABEL[audioStatus] }}
    </span>

    <button
      v-if="audioStatus === 'ready' || audioStatus === 'stale'"
      type="button"
      data-testid="play"
      class="rounded-full bg-indigo-600 p-1.5 text-white hover:bg-indigo-500"
      aria-label="Play"
      @click="onPlay"
    >
      ▶
    </button>

    <button
      v-if="audioStatus === 'stale'"
      type="button"
      data-testid="regenerate"
      class="rounded-md px-2 py-1 text-xs text-amber-700 hover:bg-amber-50"
      @click="onRegenerate"
    >
      Regenerate
    </button>

    <button
      v-if="audioStatus === 'ready'"
      type="button"
      data-testid="delete-row"
      class="rounded-md p-1 text-slate-500 hover:bg-red-50 hover:text-red-600"
      aria-label="Delete audio"
      @click="onDelete"
    >
      🗑
    </button>
  </div>
</template>
