<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import CustomEditor from './CustomEditor.vue'
import ThemeGrid from './ThemeGrid.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const store = useReaderSettingsStore()

const popoverRef = ref<HTMLElement | null>(null)
const gridRef = ref<InstanceType<typeof ThemeGrid> | null>(null)

function findGearButton(): HTMLElement | null {
  return document.querySelector('[aria-label="Reader settings"]') as HTMLElement | null
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && store.popoverOpen) {
    store.popoverOpen = false
    findGearButton()?.focus()
  }
}

function onMousedown(e: MouseEvent) {
  if (!store.popoverOpen) return
  const target = e.target as Node | null
  if (!target) return
  if (popoverRef.value?.contains(target)) return
  if (findGearButton()?.contains(target)) return
  store.popoverOpen = false
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('mousedown', onMousedown)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('mousedown', onMousedown)
})

watch(
  () => store.editingCustom,
  async (open, wasOpen) => {
    if (wasOpen && !open && store.popoverOpen) {
      await nextTick()
      gridRef.value?.focusActiveCard()
    }
  },
)
</script>

<template>
  <div v-if="store.popoverOpen" ref="popoverRef" class="settings-popover">
    <header class="settings-header">
      <h2>Reader Settings</h2>
      <button class="close-btn" type="button" aria-label="Close" @click="store.popoverOpen = false">
        ×
      </button>
    </header>

    <ThemeGrid ref="gridRef" />

    <CustomEditor v-if="store.editingCustom && store.appliedPresetKey === 'custom'" />

    <div class="settings-section toggle-row">
      <label class="toggle-cell">
        <input
          type="checkbox"
          :checked="store.highlightsVisible"
          @change="store.highlightsVisible = ($event.target as HTMLInputElement).checked"
        />
        <span>Show highlights inline</span>
      </label>
      <label class="toggle-cell">
        <span>Annotations scope</span>
        <select
          :value="store.annotationsScope"
          @change="
            store.annotationsScope = ($event.target as HTMLSelectElement).value as
              | 'current'
              | 'all'
          "
        >
          <option value="current">Current section</option>
          <option value="all">All sections</option>
        </select>
      </label>
    </div>
  </div>
</template>

<style scoped>
.settings-popover {
  position: absolute;
  right: 0;
  top: 100%;
  width: 400px;
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 0.75rem;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  padding: 1rem;
  z-index: 100;
  max-height: 85vh;
  overflow-y: auto;
}
.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}
.settings-header h2 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}
.close-btn {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--color-text-secondary, #666);
}
.settings-section {
  margin-top: 0.75rem;
}
.toggle-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.toggle-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}
</style>
