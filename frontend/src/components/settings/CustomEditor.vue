<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import ColorSwatchRow from './ColorSwatchRow.vue'
import Stepper from './ValueStepper.vue'
import ContrastBadge from '@/components/common/ContrastBadge.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const store = useReaderSettingsStore()

const BG_PALETTE = ['#ffffff', '#f4ecd8', '#0b1020', '#000000', '#fafaf6', '#fef3c7', '#ecfdf5']
const FG_PALETTE = ['#111827', '#3a2e1a', '#e5e7eb', '#cbd5e1', '#1f2937', '#000000', '#f8fafc']
const FONTS = ['Georgia', 'Inter', 'Merriweather', 'Fira Code', 'Lora', 'Source Serif Pro']

const activeBg = computed(
  () => store.pendingCustom?.bg || store.customTheme?.bg || '#ffffff',
)
const activeFg = computed(
  () => store.pendingCustom?.fg || store.customTheme?.fg || '#111827',
)
const activeAccent = computed(
  () => store.pendingCustom?.accent || store.customTheme?.accent || '#4f46e5',
)

function stagePatch(patch: Partial<{ bg: string; fg: string; accent: string }>) {
  const base = store.pendingCustom ||
    store.customTheme || {
      name: 'Custom',
      bg: '#ffffff',
      fg: '#111827',
      accent: '#4f46e5',
    }
  store.stageCustom({ ...base, ...patch })
}

function commit() {
  store.saveCustom()
  store.applyCustom()
}

function revert() {
  store.discardCustom()
}

const bgRowEl = ref<HTMLElement | null>(null)

onMounted(async () => {
  await nextTick()
  const firstSwatch = bgRowEl.value?.querySelector('button') as HTMLElement | null
  firstSwatch?.focus()
})
</script>

<template>
  <div class="custom-editor">
    <div ref="bgRowEl">
      <label class="setting-label">Background</label>
      <ColorSwatchRow
        :palette="BG_PALETTE"
        :model-value="activeBg"
        ariaLabelPrefix="Background"
        @update:model-value="(v: string) => stagePatch({ bg: v })"
      />
    </div>

    <label class="setting-label">Foreground</label>
    <ColorSwatchRow
      :palette="FG_PALETTE"
      :model-value="activeFg"
      ariaLabelPrefix="Foreground"
      @update:model-value="(v: string) => stagePatch({ fg: v })"
    />

    <label class="setting-label">Accent</label>
    <input
      type="color"
      class="color-input"
      :value="activeAccent"
      aria-label="Accent colour"
      @input="stagePatch({ accent: ($event.target as HTMLInputElement).value })"
    />

    <label class="setting-label">Font</label>
    <select
      class="setting-select"
      :value="store.currentSettings.font_family"
      @change="store.updateSetting('font_family', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="f in FONTS" :key="f" :value="f">{{ f }}</option>
    </select>

    <label class="setting-label">Size</label>
    <Stepper
      :model-value="store.currentSettings.font_size_px"
      :step="1"
      :format="(v: number) => `${v}px`"
      ariaLabel="Size"
      @update:model-value="(v: number) => store.updateSetting('font_size_px', v)"
    />

    <label class="setting-label">Line Spacing</label>
    <Stepper
      :model-value="store.currentSettings.line_spacing"
      :step="0.1"
      :format="(v: number) => v.toFixed(1)"
      ariaLabel="Line Spacing"
      @update:model-value="(v: number) => store.updateSetting('line_spacing', v)"
    />

    <label class="setting-label">Content Width</label>
    <Stepper
      :model-value="store.currentSettings.content_width_px"
      :step="40"
      :format="(v: number) => `${v}px`"
      ariaLabel="Content Width"
      @update:model-value="(v: number) => store.updateSetting('content_width_px', v)"
    />

    <div class="contrast-preview">
      <ContrastBadge :fg="activeFg" :bg="activeBg" />
    </div>

    <label class="setting-label">Preview</label>
    <div
      class="live-preview"
      :style="{
        background: activeBg,
        color: activeFg,
        fontFamily: store.currentSettings.font_family,
        fontSize: store.currentSettings.font_size_px + 'px',
        lineHeight: store.currentSettings.line_spacing,
      }"
    >
      The quick brown fox jumps over the lazy dog.
    </div>

    <div class="actions-row">
      <span v-if="store.dirty" class="dirty-hint">Custom theme preview (not saved)</span>
      <span v-else />
      <div class="actions-buttons">
        <button type="button" class="btn-secondary" :disabled="!store.dirty" @click="revert">
          Revert
        </button>
        <button type="button" class="btn-primary" :disabled="!store.dirty" @click="commit">
          Save
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-editor {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  display: flex;
  flex-direction: column;
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
.live-preview {
  margin-top: 0.25rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 0.375rem;
}
.actions-row {
  margin-top: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.dirty-hint {
  font-size: 0.75rem;
  color: var(--color-text-secondary, #666);
}
.actions-buttons {
  display: flex;
  gap: 0.5rem;
}
.btn-primary,
.btn-secondary {
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.btn-primary {
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border: none;
}
.btn-secondary {
  background: none;
  border: 1px solid var(--color-border, #ddd);
}
.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
