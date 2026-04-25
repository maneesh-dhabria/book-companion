<script setup lang="ts">
import { computed } from 'vue'

import PresetCards from './PresetCards.vue'
import StickySaveBar from '@/components/common/StickySaveBar.vue'
import ContrastBadge from '@/components/common/ContrastBadge.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const store = useReaderSettingsStore()

const fonts = ['Georgia', 'Inter', 'Merriweather', 'Fira Code', 'Lora', 'Source Serif Pro']

// FR-B1.x — six shipped theme labels. The 6-card picker stays here as a
// secondary surface alongside <PresetCards>; clicks resolve to
// store.applyPreset(matchByName.id) so this surface and PresetCards
// agree on the same appliedPresetKey state machine.
interface ThemePreset {
  id: string
  label: string
  bg: string
  fg: string
  accent: string
}

const shippedThemes: ThemePreset[] = [
  { id: 'light', label: 'Light', bg: '#ffffff', fg: '#111827', accent: '#4f46e5' },
  { id: 'sepia', label: 'Sepia', bg: '#f4ecd8', fg: '#3a2e1a', accent: '#b45309' },
  { id: 'dark', label: 'Dark', bg: '#0b1020', fg: '#e5e7eb', accent: '#93c5fd' },
  { id: 'night', label: 'Night', bg: '#000000', fg: '#cbd5e1', accent: '#60a5fa' },
  { id: 'paper', label: 'Paper', bg: '#fafaf6', fg: '#1f2937', accent: '#065f46' },
  { id: 'contrast', label: 'High Contrast', bg: '#ffffff', fg: '#000000', accent: '#b91c1c' },
]

const bgPalette = ['#ffffff', '#f4ecd8', '#0b1020', '#000000', '#fafaf6', '#fef3c7', '#ecfdf5']
const fgPalette = ['#111827', '#3a2e1a', '#e5e7eb', '#cbd5e1', '#1f2937', '#000000', '#f8fafc']

const activeCustomBg = computed(() =>
  store.pendingCustom?.bg || store.customTheme?.bg || '#ffffff',
)
const activeCustomFg = computed(() =>
  store.pendingCustom?.fg || store.customTheme?.fg || '#111827',
)
const activeCustomAccent = computed(() =>
  store.pendingCustom?.accent || store.customTheme?.accent || '#4f46e5',
)

function isThemeActive(t: ThemePreset): boolean {
  const match = store.presets.find((p) => p.name.toLowerCase() === t.label.toLowerCase())
  return match ? store.appliedPresetKey === `system:${match.id}` : false
}

function applyShippedTheme(preset: ThemePreset) {
  const match = store.presets.find(
    (p) => p.name.toLowerCase() === preset.label.toLowerCase(),
  )
  if (!match) {
    console.warn(`No preset named "${preset.label}" — popover theme click ignored`)
    return
  }
  store.editingCustom = false
  store.applyPreset(match.id)
  store.discardCustom()
}

function stagePatch(patch: Partial<{ bg: string; fg: string; accent: string }>) {
  const base = store.pendingCustom || store.customTheme || {
    name: 'Custom',
    bg: '#ffffff',
    fg: '#111827',
    accent: '#4f46e5',
  }
  store.stageCustom({ ...base, ...patch })
}

function commitCustom() {
  store.saveCustom()
  store.applyCustom()
  store.editingCustom = false
}

function revertCustom() {
  store.discardCustom()
  store.editingCustom = false
}

function adjustValue(
  key: 'font_size_px' | 'line_spacing' | 'content_width_px',
  delta: number,
) {
  const current = store.currentSettings[key]
  store.updateSetting(key, Number(current) + delta)
}
</script>

<template>
  <div class="settings-popover" v-if="store.popoverOpen">
    <div class="settings-header">
      <h2>Reader Settings</h2>
      <button class="close-btn" @click="store.popoverOpen = false">×</button>
    </div>

    <PresetCards />

    <!-- T24 — 6-card theme picker + Custom slot -->
    <div class="settings-section">
      <label class="setting-label">Theme</label>
      <div class="theme-grid">
        <button
          v-for="t in shippedThemes"
          :key="t.id"
          type="button"
          class="theme-card"
          :class="{ active: isThemeActive(t) }"
          :style="{ background: t.bg, color: t.fg, borderColor: t.accent }"
          @click="applyShippedTheme(t)"
        >
          <span class="theme-card-label">{{ t.label }}</span>
          <span class="theme-card-sample">Aa</span>
        </button>
      </div>
    </div>

    <!-- FR-B2 — bg/fg/accent colour palettes, visible only while editing Custom -->
    <div v-if="store.editingCustom" class="settings-section custom-editor">
      <label class="setting-label">Background</label>
      <div class="swatch-row">
        <button
          v-for="c in bgPalette"
          :key="c"
          class="swatch"
          :class="{ active: activeCustomBg === c }"
          :style="{ background: c }"
          :aria-label="`Background ${c}`"
          @click="stagePatch({ bg: c })"
        />
      </div>

      <label class="setting-label">Foreground</label>
      <div class="swatch-row">
        <button
          v-for="c in fgPalette"
          :key="c"
          class="swatch"
          :class="{ active: activeCustomFg === c }"
          :style="{ background: c }"
          :aria-label="`Foreground ${c}`"
          @click="stagePatch({ fg: c })"
        />
      </div>

      <label class="setting-label">Accent (picker)</label>
      <input
        type="color"
        :value="activeCustomAccent"
        class="color-input"
        @input="stagePatch({ accent: ($event.target as HTMLInputElement).value })"
      />

      <div class="contrast-preview">
        <ContrastBadge :fg="activeCustomFg" :bg="activeCustomBg" />
      </div>
    </div>

    <div class="settings-section">
      <label class="setting-label">Font</label>
      <select
        :value="store.currentSettings.font_family"
        @change="store.updateSetting('font_family', ($event.target as HTMLSelectElement).value)"
        class="setting-select"
      >
        <option v-for="font in fonts" :key="font" :value="font">{{ font }}</option>
      </select>
    </div>

    <div class="settings-section">
      <label class="setting-label">Size</label>
      <div class="stepper">
        <button @click="adjustValue('font_size_px', -1)">−</button>
        <span>{{ store.currentSettings.font_size_px }}px</span>
        <button @click="adjustValue('font_size_px', 1)">+</button>
      </div>
    </div>

    <div class="settings-section">
      <label class="setting-label">Line Spacing</label>
      <div class="stepper">
        <button @click="adjustValue('line_spacing', -0.1)">−</button>
        <span>{{ store.currentSettings.line_spacing.toFixed(1) }}</span>
        <button @click="adjustValue('line_spacing', 0.1)">+</button>
      </div>
    </div>

    <div class="settings-section">
      <label class="setting-label">Content Width</label>
      <div class="stepper">
        <button @click="adjustValue('content_width_px', -40)">−</button>
        <span>{{ store.currentSettings.content_width_px }}px</span>
        <button @click="adjustValue('content_width_px', 40)">+</button>
      </div>
    </div>

    <!-- v1.5 toggles in the store: highlightsVisible + annotationsScope -->
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
          @change="store.annotationsScope = ($event.target as HTMLSelectElement).value as any"
        >
          <option value="current">Current section</option>
          <option value="all">All sections</option>
        </select>
      </label>
    </div>

    <div class="settings-section preview">
      <label class="setting-label">Preview</label>
      <div
        class="live-preview"
        :style="{
          fontFamily: store.currentSettings.font_family,
          fontSize: store.currentSettings.font_size_px + 'px',
          lineHeight: store.currentSettings.line_spacing,
          maxWidth: store.currentSettings.content_width_px + 'px',
        }"
      >
        The quick brown fox jumps over the lazy dog. This is a preview of your reading settings.
      </div>
    </div>

    <StickySaveBar
      v-if="store.editingCustom"
      :dirty="store.dirty"
      :can-revert="true"
      @save="commitCustom"
      @revert="revertCustom"
    >
      <template #label>Custom theme preview (not saved yet)</template>
      <template #save-label>Save &amp; apply</template>
    </StickySaveBar>
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
.setting-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary, #666);
  margin: 0.5rem 0 0.25rem;
}
.setting-select {
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  font-size: 0.875rem;
}
.stepper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.stepper button {
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  background: var(--color-bg, #fff);
  cursor: pointer;
}
.stepper span {
  font-size: 0.875rem;
  min-width: 3rem;
  text-align: center;
}
.theme-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}
.theme-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  padding: 0.5rem 0.55rem;
  border: 2px solid transparent;
  border-radius: 0.5rem;
  cursor: pointer;
  text-align: left;
  font-size: 0.8125rem;
}
.theme-card.active {
  outline: 2px solid #4f46e5;
  outline-offset: 2px;
}
.theme-card-label {
  font-weight: 600;
  font-size: 0.75rem;
}
.theme-card-sample {
  font-size: 1.1rem;
  font-weight: 700;
}
.custom-editor {
  padding: 0.5rem;
  background: #f8fafc;
  border-radius: 0.375rem;
}
.swatch-row {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.swatch {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
}
.swatch.active {
  border-color: #4f46e5;
}
.color-input {
  width: 4rem;
  height: 1.75rem;
  border: 1px solid #d1d5db;
  padding: 0;
  cursor: pointer;
}
.contrast-preview {
  margin-top: 0.5rem;
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
.live-preview {
  margin-top: 0.25rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 0.375rem;
}
.settings-footer {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.save-btn {
  padding: 0.375rem 0.75rem;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.8rem;
}
.cancel-btn {
  padding: 0.375rem 0.75rem;
  background: none;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.8rem;
}
.save-input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 0.375rem;
  font-size: 0.8rem;
}
</style>
