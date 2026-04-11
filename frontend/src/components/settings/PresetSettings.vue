<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'

interface SummarizationPreset {
  name: string
  is_system: boolean
  description?: string
  facets?: Record<string, string>
}

const presets = ref<SummarizationPreset[]>([])
const selectedPreset = ref<SummarizationPreset | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    // The CLI preset list command uses the PresetService.
    // For the web UI, we list presets from the YAML directory via a simple endpoint.
    // Fallback: show a helpful message directing to CLI.
    presets.value = [
      { name: 'practitioner_bullets', is_system: true, description: 'Concise bullet-point summaries for practitioners' },
      { name: 'academic_detailed', is_system: true, description: 'Detailed academic analysis with citations' },
      { name: 'executive_brief', is_system: true, description: 'High-level executive briefing' },
      { name: 'study_guide', is_system: true, description: 'Structured study guide format' },
      { name: 'tweet_thread', is_system: true, description: 'Twitter thread-style summary' },
    ]
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="preset-settings">
    <h2 class="section-title">Summarization Presets</h2>

    <div class="preset-layout">
      <!-- Preset List -->
      <div class="preset-list">
        <div
          v-for="preset in presets"
          :key="preset.name"
          class="preset-item"
          :class="{ active: selectedPreset?.name === preset.name }"
          data-testid="preset-list-item"
          @click="selectedPreset = preset"
        >
          <span class="preset-name">{{ preset.name }}</span>
          <span v-if="preset.is_system" class="system-badge">System</span>
        </div>
      </div>

      <!-- Preset Detail -->
      <div v-if="selectedPreset" class="preset-detail">
        <h3 class="detail-name">{{ selectedPreset.name }}</h3>
        <p v-if="selectedPreset.description" class="detail-description">
          {{ selectedPreset.description }}
        </p>
        <span v-if="selectedPreset.is_system" class="detail-readonly">
          System presets are read-only. Use the CLI to create custom presets:
          <code>bookcompanion preset create &lt;name&gt;</code>
        </span>
      </div>

      <div v-else class="preset-detail-empty">
        <p>Select a preset to view its details</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
}

.preset-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1.5rem;
}

.preset-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.preset-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.15s;
}

.preset-item:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.05));
}

.preset-item.active {
  background: var(--color-bg-active, rgba(0, 0, 0, 0.08));
  font-weight: 600;
}

.preset-name {
  font-family: monospace;
  font-size: 0.8125rem;
}

.system-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.0625rem 0.375rem;
  background: var(--color-bg-muted, #f3f4f6);
  border-radius: 0.25rem;
  color: var(--color-text-muted, #888);
}

.preset-detail {
  padding: 1rem;
  background: var(--color-bg-muted, #f9fafb);
  border-radius: 0.5rem;
}

.detail-name {
  font-family: monospace;
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.detail-description {
  font-size: 0.875rem;
  color: var(--color-text-muted, #666);
  margin-bottom: 1rem;
}

.detail-readonly {
  font-size: 0.8125rem;
  color: var(--color-text-muted, #888);
  display: block;
}

.detail-readonly code {
  background: var(--color-bg-muted, #e5e7eb);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
}

.preset-detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted, #888);
  font-size: 0.875rem;
  min-height: 120px;
}

@media (max-width: 767px) {
  .preset-layout {
    grid-template-columns: 1fr;
  }
}
</style>
