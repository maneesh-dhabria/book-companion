<script setup lang="ts">
import { computed } from 'vue'

import { useReaderSettingsStore } from '@/stores/readerSettings'

const store = useReaderSettingsStore()

const isCustomActive = computed(() => store.appliedPresetKey === 'custom')

function isSystemActive(id: number): boolean {
  return store.appliedPresetKey === `system:${id}`
}

function swatchColor(theme: string): string {
  if (theme === 'dark') return '#1e1e2e'
  if (theme === 'night') return '#0f172a'
  if (theme === 'sepia') return '#fbf0d9'
  if (theme === 'paper') return '#fafaf5'
  if (theme === 'contrast') return '#000000'
  return '#ffffff'
}

function customSwatchStyle() {
  const slot = store.customTheme
  if (!slot) {
    return {
      background: 'linear-gradient(135deg, #f3f4f6 0%, #d1d5db 100%)',
    }
  }
  return { backgroundColor: slot.bg }
}

function onCustomClick() {
  if (isCustomActive.value) {
    // Subsequent click on the already-active Custom card re-applies it
    // (e.g. so the user gets the live colours back if currentSettings drifted).
    store.applyCustom()
  } else {
    // First-edit: apply Custom + open the picker so the swatch editor is visible.
    store.openCustomPicker()
  }
}
</script>

<template>
  <div class="preset-cards">
    <div class="preset-grid">
      <button
        v-for="preset in store.presets"
        :key="preset.id"
        class="preset-card"
        :class="{ active: isSystemActive(preset.id) }"
        @click="store.applyPreset(preset.id)"
      >
        <div class="preset-swatch" :style="{ backgroundColor: swatchColor(preset.theme) }" />
        <span class="preset-name">{{ preset.name }}</span>
        <span class="preset-font">{{ preset.font_family }} {{ preset.font_size_px }}px</span>
        <span v-if="isSystemActive(preset.id)" class="preset-check" aria-label="Active">✓</span>
      </button>

      <button
        class="preset-card"
        :class="{ active: isCustomActive }"
        @click="onCustomClick"
      >
        <div class="preset-swatch" :style="customSwatchStyle()" />
        <span class="preset-name">Custom</span>
        <span class="preset-font">Tap to edit</span>
        <span
          v-if="isCustomActive"
          class="preset-check preset-check--custom"
          aria-label="Active"
        >✓</span>
        <button
          v-if="isCustomActive"
          type="button"
          class="preset-pencil"
          aria-label="Edit custom theme"
          @click.stop="store.openCustomPicker()"
        >✎</button>
      </button>
    </div>
  </div>
</template>

<style scoped>
.preset-cards { padding: 0.5rem 0; }
.preset-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
.preset-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 0.5rem;
  background: var(--color-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s;
  text-align: center;
}
.preset-card:hover { border-color: var(--color-primary, #3b82f6); }
.preset-card.active { border-color: var(--color-primary, #3b82f6); border-width: 2px; }
.preset-swatch {
  width: 100%;
  height: 24px;
  border-radius: 0.25rem;
  border: 1px solid var(--color-border, #e0e0e0);
}
.preset-name { font-size: 0.8rem; font-weight: 500; }
.preset-font { font-size: 0.7rem; color: var(--color-text-secondary, #888); }
.preset-check {
  position: absolute;
  top: 0.25rem;
  right: 0.25rem;
  color: var(--color-primary, #3b82f6);
  font-weight: bold;
}
/* FR-F4.16: Custom card moves checkmark to top-left to make room for the
 * top-right pencil. */
.preset-check--custom {
  right: auto;
  left: 0.25rem;
}
.preset-pencil {
  position: absolute;
  top: 0.25rem;
  right: 0.25rem;
  background: none;
  border: none;
  color: var(--color-text-secondary, #6b7280);
  cursor: pointer;
  font-size: 0.95rem;
  line-height: 1;
  padding: 2px 4px;
}
.preset-pencil:hover { color: var(--color-primary, #3b82f6); }
</style>
