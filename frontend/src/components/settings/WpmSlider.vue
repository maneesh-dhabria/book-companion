<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { apiClient } from '@/api/client'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  label: string
  min: number
  max: number
  step: number
  modelValue: number
  settingsPath: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const localValue = ref<number>(props.modelValue)
const saving = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    if (!saving.value) localValue.value = v
  },
)

const valueText = computed(() => `${localValue.value} wpm`)

// Build a nested object body from a dot-path: "tts.listen_wpm" + 225 →
// {tts: {listen_wpm: 225}}.
function buildBody(path: string, value: number): Record<string, unknown> {
  const parts = path.split('.').filter(Boolean)
  const root: Record<string, unknown> = {}
  let cursor: Record<string, unknown> = root
  for (let i = 0; i < parts.length - 1; i++) {
    const next: Record<string, unknown> = {}
    cursor[parts[i]] = next
    cursor = next
  }
  cursor[parts[parts.length - 1]] = value
  return root
}

async function onChange(ev: Event) {
  const target = ev.target as HTMLInputElement
  const next = Number(target.value)
  localValue.value = next
  emit('update:modelValue', next)

  saving.value = true
  try {
    await apiClient.patch('/settings', buildBody(props.settingsPath, next))
  } catch {
    const ui = useUiStore()
    ui.showToast(`Failed to save ${props.label.toLowerCase()}`, 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <label class="wpm-slider flex items-center gap-3 text-sm text-slate-700">
    <span class="min-w-[8rem]">{{ label }}</span>
    <input
      type="range"
      :min="min"
      :max="max"
      :step="step"
      :value="localValue"
      :data-testid="`wpm-slider-${settingsPath.replace(/\./g, '-')}`"
      @change="onChange"
    />
    <span class="min-w-[5rem] text-xs text-slate-500">{{ valueText }}</span>
  </label>
</template>
