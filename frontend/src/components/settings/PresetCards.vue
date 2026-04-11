<script setup lang="ts">
import { useReaderSettingsStore } from '@/stores/readerSettings'
import type { ReadingPreset } from '@/types'
import { computed } from 'vue'

const store = useReaderSettingsStore()

const systemPresets = computed(() => store.presets.filter((p) => p.is_system))
const userPresets = computed(() => store.presets.filter((p) => !p.is_system))
</script>

<template>
  <div class="preset-cards">
    <h3 class="preset-section-title">System Presets</h3>
    <div class="preset-grid">
      <button
        v-for="preset in systemPresets"
        :key="preset.id"
        class="preset-card"
        :class="{ active: store.activePreset?.id === preset.id }"
        @click="store.applyPreset(preset.id)"
      >
        <div
          class="preset-swatch"
          :style="{ backgroundColor: preset.theme === 'dark' ? '#1e1e2e' : preset.theme === 'sepia' ? '#fbf0d9' : '#ffffff' }"
        />
        <span class="preset-name">{{ preset.name }}</span>
        <span class="preset-font">{{ preset.font_family }} {{ preset.font_size_px }}px</span>
        <span v-if="store.activePreset?.id === preset.id" class="preset-check">✓</span>
      </button>
    </div>

    <template v-if="userPresets.length">
      <h3 class="preset-section-title">Your Presets</h3>
      <div class="preset-grid">
        <button
          v-for="preset in userPresets"
          :key="preset.id"
          class="preset-card"
          :class="{ active: store.activePreset?.id === preset.id }"
          @click="store.applyPreset(preset.id)"
        >
          <div class="preset-swatch" :style="{ backgroundColor: preset.theme === 'dark' ? '#1e1e2e' : '#ffffff' }" />
          <span class="preset-name">{{ preset.name }}</span>
          <span class="preset-font">{{ preset.font_family }} {{ preset.font_size_px }}px</span>
          <span v-if="store.activePreset?.id === preset.id" class="preset-check">✓</span>
          <button class="preset-delete" @click.stop="store.deletePreset(preset.id)">×</button>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.preset-cards { padding: 0.5rem 0; }
.preset-section-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary, #666); margin: 0.75rem 0 0.5rem; }
.preset-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
.preset-card { position: relative; display: flex; flex-direction: column; align-items: center; gap: 0.25rem; padding: 0.75rem; border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.5rem; background: var(--color-bg, #fff); cursor: pointer; transition: border-color 0.15s; text-align: center; }
.preset-card:hover { border-color: var(--color-primary, #3b82f6); }
.preset-card.active { border-color: var(--color-primary, #3b82f6); border-width: 2px; }
.preset-swatch { width: 100%; height: 24px; border-radius: 0.25rem; border: 1px solid var(--color-border, #e0e0e0); }
.preset-name { font-size: 0.8rem; font-weight: 500; }
.preset-font { font-size: 0.7rem; color: var(--color-text-secondary, #888); }
.preset-check { position: absolute; top: 0.25rem; right: 0.25rem; color: var(--color-primary, #3b82f6); font-weight: bold; }
.preset-delete { position: absolute; top: 0.25rem; right: 0.25rem; background: none; border: none; color: var(--color-text-secondary, #888); cursor: pointer; font-size: 1rem; line-height: 1; }
.preset-delete:hover { color: var(--color-danger, #ef4444); }
</style>
