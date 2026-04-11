<script setup lang="ts">
import PresetCards from './PresetCards.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'
import { ref } from 'vue'

const store = useReaderSettingsStore()
const savePresetName = ref('')
const showSaveInput = ref(false)

const fonts = ['Georgia', 'Inter', 'Merriweather', 'Fira Code', 'Lora', 'Source Serif Pro']

function adjustValue(key: 'font_size_px' | 'line_spacing' | 'content_width_px', delta: number) {
  const current = store.currentSettings[key]
  store.updateSetting(key, Number(current) + delta)
}

async function savePreset() {
  if (!savePresetName.value.trim()) return
  await store.saveAsPreset(savePresetName.value.trim())
  savePresetName.value = ''
  showSaveInput.value = false
}
</script>

<template>
  <div class="settings-popover" v-if="store.popoverOpen">
    <div class="settings-header">
      <h2>Reader Settings</h2>
      <button class="close-btn" @click="store.popoverOpen = false">×</button>
    </div>

    <PresetCards />

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

    <div class="settings-section">
      <label class="setting-label">Theme</label>
      <div class="theme-swatches">
        <button
          v-for="theme in ['light', 'sepia', 'dark']"
          :key="theme"
          class="theme-swatch"
          :class="{ active: store.currentSettings.theme === theme }"
          @click="store.updateSetting('theme', theme)"
        >
          {{ theme }}
        </button>
      </div>
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

    <div class="settings-footer">
      <template v-if="!showSaveInput">
        <button class="save-btn" @click="showSaveInput = true">Save as Preset</button>
      </template>
      <template v-else>
        <input v-model="savePresetName" placeholder="Preset name" class="save-input" @keyup.enter="savePreset" />
        <button class="save-btn" @click="savePreset">Save</button>
        <button class="cancel-btn" @click="showSaveInput = false">Cancel</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.settings-popover { position: absolute; right: 0; top: 100%; width: 380px; background: var(--color-bg, #fff); border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.75rem; box-shadow: 0 8px 30px rgba(0,0,0,0.12); padding: 1rem; z-index: 100; max-height: 80vh; overflow-y: auto; }
.settings-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.settings-header h2 { font-size: 1rem; font-weight: 600; margin: 0; }
.close-btn { background: none; border: none; font-size: 1.25rem; cursor: pointer; color: var(--color-text-secondary, #666); }
.settings-section { margin-top: 0.75rem; }
.setting-label { display: block; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary, #666); margin-bottom: 0.25rem; }
.setting-select { width: 100%; padding: 0.375rem 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; font-size: 0.875rem; }
.stepper { display: flex; align-items: center; gap: 0.5rem; }
.stepper button { width: 2rem; height: 2rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: var(--color-bg, #fff); cursor: pointer; font-size: 1rem; display: flex; align-items: center; justify-content: center; }
.stepper span { font-size: 0.875rem; min-width: 3rem; text-align: center; }
.theme-swatches { display: flex; gap: 0.5rem; }
.theme-swatch { padding: 0.375rem 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; cursor: pointer; text-transform: capitalize; font-size: 0.8rem; }
.theme-swatch.active { border-color: var(--color-primary, #3b82f6); background: var(--color-primary-light, #eff6ff); }
.live-preview { margin-top: 0.25rem; padding: 0.75rem; border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.375rem; }
.settings-footer { margin-top: 1rem; display: flex; gap: 0.5rem; align-items: center; }
.save-btn { padding: 0.375rem 0.75rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; font-size: 0.8rem; }
.cancel-btn { padding: 0.375rem 0.75rem; background: none; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; cursor: pointer; font-size: 0.8rem; }
.save-input { flex: 1; padding: 0.375rem 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; font-size: 0.8rem; }
</style>
