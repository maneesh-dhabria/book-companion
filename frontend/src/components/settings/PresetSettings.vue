<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'
import PresetCreateEditForm from './PresetCreateEditForm.vue'
import PresetTemplateViewer from './PresetTemplateViewer.vue'

interface PresetItem {
  id: string
  label: string
  description: string
  facets: Record<string, string>
  system: boolean
}
interface PresetWarning {
  file: string
  error: string
}
interface PresetListResponse {
  presets: PresetItem[]
  default_id: string | null
  warnings?: PresetWarning[]
}

const presets = ref<PresetItem[]>([])
const warnings = ref<PresetWarning[]>([])
const selectedId = ref<string | null>(null)
const loading = ref(false)
const showFormModal = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formError = ref<string | null>(null)
const deleteCandidate = ref<string | null>(null)
const deleteTimer = ref<number | null>(null)

const FACET_DIMENSIONS: Record<string, string[]> = {
  style: [
    'bullet_points',
    'narrative',
    'podcast_dialogue',
    'cornell_notes',
    'mind_map_outline',
    'tweet_thread',
  ],
  audience: ['practitioner', 'academic', 'executive'],
  compression: ['brief', 'standard', 'detailed'],
  content_focus: ['key_concepts', 'frameworks_examples', 'full_coverage'],
}

const selected = computed(() => presets.value.find((p) => p.id === selectedId.value) ?? null)

async function fetchPresets() {
  loading.value = true
  try {
    const r = await apiClient.get<PresetListResponse>('/summarize/presets')
    presets.value = r.presets || []
    warnings.value = r.warnings || []
    if (selectedId.value && !presets.value.find((p) => p.id === selectedId.value)) {
      selectedId.value = presets.value[0]?.id ?? null
    } else if (!selectedId.value) {
      selectedId.value = r.default_id ?? presets.value[0]?.id ?? null
    }
  } catch {
    presets.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchPresets)

function openCreate() {
  formMode.value = 'create'
  formError.value = null
  showFormModal.value = true
}
function openEdit() {
  if (!selected.value) return
  formMode.value = 'edit'
  formError.value = null
  showFormModal.value = true
}
function closeForm() {
  showFormModal.value = false
  formError.value = null
}

async function onSave(payload: {
  name: string
  label: string
  description: string
  facets: Record<string, string>
}) {
  formError.value = null
  try {
    if (formMode.value === 'create') {
      await apiClient.post('/summarize/presets', payload)
    } else {
      await apiClient.put(`/summarize/presets/${encodeURIComponent(payload.name)}`, payload)
    }
    closeForm()
    selectedId.value = payload.name
    await fetchPresets()
  } catch (e) {
    const err = e as Error & { status?: number; detail?: unknown }
    if (err.status === 409) formError.value = 'A preset with this name already exists.'
    else if (err.status === 422)
      formError.value =
        typeof err.detail === 'string' ? err.detail : err.message || 'Invalid input.'
    else formError.value = err.message || 'Save failed.'
  }
}

function startDelete(id: string) {
  if (deleteCandidate.value === id) {
    confirmDelete(id)
    return
  }
  deleteCandidate.value = id
  if (deleteTimer.value) window.clearTimeout(deleteTimer.value)
  deleteTimer.value = window.setTimeout(() => {
    deleteCandidate.value = null
    deleteTimer.value = null
  }, 5000)
}

async function confirmDelete(id: string) {
  if (deleteTimer.value) window.clearTimeout(deleteTimer.value)
  deleteCandidate.value = null
  deleteTimer.value = null
  try {
    await apiClient.delete(`/summarize/presets/${encodeURIComponent(id)}`)
    if (selectedId.value === id) selectedId.value = null
    await fetchPresets()
  } catch {
    // Ignore — surface a toast in a richer impl.
  }
}

const initialPayload = computed(() =>
  selected.value
    ? {
        name: selected.value.id,
        label: selected.value.label,
        description: selected.value.description,
        facets: selected.value.facets,
      }
    : null,
)
</script>

<template>
  <div class="preset-settings">
    <header class="header-row">
      <h2 class="section-title">Summarization Presets</h2>
      <button class="btn-primary" type="button" @click="openCreate">+ New preset</button>
    </header>

    <div v-if="warnings.length > 0" class="warnings-banner">
      <strong>{{ warnings.length }}</strong> preset file(s) skipped due to errors.
      <ul>
        <li v-for="w in warnings" :key="w.file">
          <code>{{ w.file }}</code> — {{ w.error }}
        </li>
      </ul>
    </div>

    <div class="preset-layout">
      <ul class="preset-list">
        <li
          v-for="preset in presets"
          :key="preset.id"
          class="preset-item"
          :class="{ active: selectedId === preset.id }"
          @click="selectedId = preset.id"
        >
          <span class="preset-name">{{ preset.label }}</span>
          <span v-if="preset.system" class="system-badge">System</span>
          <span v-else class="preset-actions">
            <button type="button" class="link-btn" @click.stop="selectedId = preset.id; openEdit()">Edit</button>
            <button
              type="button"
              class="link-btn danger"
              @click.stop="startDelete(preset.id)"
            >
              {{ deleteCandidate === preset.id ? 'Confirm delete' : 'Delete' }}
            </button>
          </span>
        </li>
      </ul>

      <div v-if="selected" class="preset-detail">
        <h3 class="detail-name">{{ selected.label }}</h3>
        <p v-if="selected.description" class="detail-description">{{ selected.description }}</p>
        <table class="facets-table">
          <tbody>
            <tr v-for="(val, dim) in selected.facets" :key="dim">
              <th>{{ String(dim) }}</th>
              <td><code>{{ val }}</code></td>
            </tr>
          </tbody>
        </table>
        <h4 class="template-heading">Prompt template</h4>
        <PresetTemplateViewer :name="selected.id" />
      </div>
      <div v-else class="preset-detail-empty">
        <p>Select a preset to view its details, or create a new one.</p>
      </div>
    </div>

    <div v-if="showFormModal" class="modal-backdrop" @click.self="closeForm">
      <div class="modal">
        <h3>{{ formMode === 'edit' ? 'Edit preset' : 'New preset' }}</h3>
        <PresetCreateEditForm
          :mode="formMode"
          :facet-options="FACET_DIMENSIONS"
          :initial="formMode === 'edit' ? initialPayload : null"
          @save="onSave"
          @cancel="closeForm"
        />
        <p v-if="formError" class="form-error">{{ formError }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}
.warnings-banner {
  background: var(--color-bg-warning, #fef3c7);
  border: 1px solid var(--color-border-warning, #fbbf24);
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 0.9em;
}
.warnings-banner ul {
  margin: 6px 0 0 18px;
}
.preset-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1.5rem;
}
.preset-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.preset-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
}
.preset-item:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.04));
}
.preset-item.active {
  background: var(--color-bg-active, rgba(0, 0, 0, 0.07));
  font-weight: 600;
}
.preset-name {
  font-family: monospace;
}
.system-badge {
  font-size: 0.7em;
  padding: 2px 6px;
  background: var(--color-bg-muted, #f3f4f6);
  border-radius: 3px;
  color: var(--color-text-muted, #666);
}
.preset-actions {
  display: flex;
  gap: 6px;
}
.link-btn {
  background: none;
  border: none;
  color: var(--color-accent, #4f46e5);
  cursor: pointer;
  font-size: 0.85em;
  padding: 0;
}
.link-btn.danger {
  color: var(--color-text-danger, #b91c1c);
}
.preset-detail {
  padding: 16px;
  background: var(--color-bg-muted, #f9fafb);
  border-radius: 8px;
}
.facets-table {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
}
.facets-table th,
.facets-table td {
  text-align: left;
  padding: 4px 6px;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.85em;
}
.facets-table th {
  width: 140px;
  font-weight: 600;
}
.template-heading {
  margin: 16px 0 8px;
  font-size: 0.9em;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}
.preset-detail-empty {
  color: var(--color-text-muted, #888);
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--color-bg-primary, white);
  padding: 24px;
  border-radius: 8px;
  width: min(560px, 90vw);
  max-height: 90vh;
  overflow: auto;
}
.modal h3 {
  margin-top: 0;
}
.form-error {
  color: var(--color-text-danger, #b91c1c);
  font-size: 0.9em;
  margin-top: 8px;
}
.btn-primary {
  background: var(--color-accent, #4f46e5);
  color: var(--color-text-on-accent, white);
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
}
@media (max-width: 767px) {
  .preset-layout {
    grid-template-columns: 1fr;
  }
}
</style>
