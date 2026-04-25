<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import * as readingPresetsApi from '@/api/readingPresets'
import type { ReadingPreset } from '@/types'

const settingsStore = useSettingsStore()
const presets = ref<ReadingPreset[]>([])
const customCss = ref('')
const saving = ref(false)

const defaultPreset = computed({
  get: () => settingsStore.settings?.summarization.default_preset ?? 'practitioner_bullets',
  set: (val: string) => {
    settingsStore.saveSettings({ summarization: { default_preset: val } } as any)
  },
})

onMounted(async () => {
  try {
    presets.value = (await readingPresetsApi.listPresets()).items
  } catch {
    // Presets API may not be available
  }
})

async function saveReadingSettings() {
  saving.value = true
  try {
    await settingsStore.saveSettings({
      summarization: { default_preset: defaultPreset.value },
    } as any)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="reading-settings">
    <h2 class="section-title">Reading Preferences</h2>

    <!-- Default Preset -->
    <div class="setting-group">
      <h3 class="group-title">Default Summarization Preset</h3>
      <select
        v-model="defaultPreset"
        class="select-input"
        data-testid="default-preset-select"
      >
        <option value="practitioner_bullets">Practitioner Bullets</option>
        <option value="academic_detailed">Academic Detailed</option>
        <option value="executive_brief">Executive Brief</option>
        <option value="study_guide">Study Guide</option>
        <option value="tweet_thread">Tweet Thread</option>
      </select>
    </div>

    <!-- Reading Presets -->
    <div v-if="presets.length > 0" class="setting-group">
      <h3 class="group-title">Reading Presets</h3>
      <div class="presets-list">
        <div
          v-for="preset in presets"
          :key="preset.id"
          class="preset-chip"
        >
          {{ preset.name }}
        </div>
      </div>
    </div>

    <!-- Custom CSS -->
    <div class="setting-group">
      <h3 class="group-title">Custom CSS</h3>
      <p class="group-description">Add custom CSS rules that will be applied to the reader.</p>
      <textarea
        v-model="customCss"
        class="css-textarea"
        data-testid="custom-css-textarea"
        placeholder="body { font-size: 18px; }"
        rows="6"
      />
    </div>

    <button
      class="btn-primary"
      :disabled="saving"
      data-testid="save-reading-settings-btn"
      @click="saveReadingSettings"
    >
      {{ saving ? 'Saving...' : 'Save' }}
    </button>
  </div>
</template>

<style scoped>
.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
}

.setting-group {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.group-title {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #888);
  margin-bottom: 0.5rem;
}

.group-description {
  font-size: 0.8125rem;
  color: var(--color-text-muted, #888);
  margin-bottom: 0.75rem;
}

.select-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--color-bg, white);
  color: var(--color-text, #333);
  min-width: 200px;
}

.presets-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preset-chip {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 1rem;
  font-size: 0.8125rem;
}

.preset-chip.active {
  border-color: var(--color-accent, #2563eb);
  background: rgba(37, 99, 235, 0.05);
}

.active-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--color-accent, #2563eb);
}

.css-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 0.375rem;
  font-family: monospace;
  font-size: 0.8125rem;
  resize: vertical;
  background: var(--color-bg, white);
  color: var(--color-text, #333);
}

.btn-primary {
  padding: 0.5rem 1.5rem;
  background: var(--color-accent, #2563eb);
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
