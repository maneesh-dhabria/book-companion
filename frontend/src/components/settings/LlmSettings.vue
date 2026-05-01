<script setup lang="ts">
/**
 * LLM provider settings panel.
 *
 * Phase H (T26) of upload+summarize UX fixes:
 *   - cli_command field replaced by config_dir (provider-routed via env vars)
 *   - Provider badges show detected/version/floor outcome from /api/v1/llm/status
 *   - Re-detect button calls /api/v1/llm/recheck to bypass the 60s cache
 *   - Banner surfaces preflight failures (binary missing, version below floor)
 */
import { computed, onMounted, ref, watchEffect } from 'vue'

import { getLlmStatus, recheckLlm, type LLMStatusResponse } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'
import { useUiStore } from '@/stores/ui'

interface ModelOption {
  id: string
  label: string
}

interface ModelsPayload {
  providers: Record<string, ModelOption[]>
  detected_provider?: string | null
  current_model?: string | null
}

const settingsStore = useSettingsStore()
const saving = ref(false)
const rechecking = ref(false)
const modelsPayload = ref<ModelsPayload | null>(null)
const llmStatus = ref<LLMStatusResponse | null>(null)
const modelValue = ref<string>('')
const customModel = ref<string>('')
const useCustom = ref(false)

const provider = computed({
  get: () => settingsStore.settings?.llm?.provider ?? 'auto',
  set: (val: string) => {
    if (settingsStore.settings?.llm) {
      settingsStore.settings.llm.provider = val
    }
  },
})

const configDir = computed({
  get: () => settingsStore.settings?.llm?.config_dir ?? '',
  set: (val: string) => {
    if (settingsStore.settings?.llm) {
      settingsStore.settings.llm.config_dir = val.trim() || null
    }
  },
})

const banner = computed(() => {
  const pf = llmStatus.value?.preflight
  if (!pf) return null
  if (!pf.ok) {
    return { tone: 'error' as const, message: pf.reason || 'LLM CLI is not available.' }
  }
  if (!pf.version_ok) {
    return { tone: 'warning' as const, message: pf.reason || 'LLM CLI version is outdated.' }
  }
  return null
})

const detectedBadge = computed(() => {
  const pf = llmStatus.value?.preflight
  if (!pf) return null
  if (!pf.binary_resolved) return { label: 'not detected', tone: 'error' as const }
  if (pf.version) {
    const tone = pf.version_ok ? ('ok' as const) : ('warning' as const)
    return { label: `${pf.binary} ${pf.version}`, tone }
  }
  return { label: pf.binary || '', tone: 'ok' as const }
})

async function loadStatus() {
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
}

async function recheck() {
  rechecking.value = true
  const ui = useUiStore()
  try {
    llmStatus.value = await recheckLlm()
    ui.showToast('LLM status re-checked', 'success')
  } catch (e) {
    ui.showToast(`Re-detect failed: ${(e as Error).message}`, 'error')
  } finally {
    rechecking.value = false
  }
}

async function save() {
  saving.value = true
  const ui = useUiStore()
  try {
    const effectiveModel = useCustom.value ? customModel.value.trim() : modelValue.value
    const cd = configDir.value
    await settingsStore.saveSettings({
      llm: {
        provider: provider.value,
        config_dir: cd ? cd : null,
        ...(effectiveModel ? { model: effectiveModel } : {}),
      } as Partial<import('@/api/settings').AppSettings['llm']>,
    } as Partial<import('@/api/settings').AppSettings>)
    ui.showToast('Settings saved', 'success')
    // PATCH invalidates the backend's preflight cache; pick up the new state.
    await loadStatus()
  } catch (e) {
    ui.showToast(`Settings save failed: ${(e as Error).message}`, 'error')
  } finally {
    saving.value = false
  }
}

const modelOptionsForProvider = computed<ModelOption[]>(() => {
  if (!modelsPayload.value) return []
  const prov = provider.value === 'auto'
    ? (modelsPayload.value.detected_provider || 'claude')
    : provider.value
  return modelsPayload.value.providers[prov] || []
})

watchEffect(() => {
  if (useCustom.value) return
  const opts = modelOptionsForProvider.value
  if (!opts.length) return
  if (!opts.some((o) => o.id === modelValue.value)) {
    modelValue.value = opts[0].id
  }
})

onMounted(async () => {
  await loadStatus()
  try {
    const resp = await fetch('/api/v1/config/models')
    if (resp.ok) {
      modelsPayload.value = await resp.json()
      const current = modelsPayload.value?.current_model || ''
      const allKnown = Object.values(modelsPayload.value?.providers || {}).flat()
      if (current && allKnown.some((o) => o.id === current)) {
        modelValue.value = current
      } else if (current) {
        useCustom.value = true
        customModel.value = current
      }
    }
  } catch {
    modelsPayload.value = null
  }
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h3 class="text-lg font-medium text-gray-900">LLM Provider</h3>
      <p class="mt-1 text-sm text-gray-500">
        Configure which AI coding assistant CLI to use for summarization and evaluation.
      </p>
    </div>

    <div
      v-if="banner"
      :class="[
        'rounded-md border p-3 text-sm',
        banner.tone === 'error'
          ? 'border-red-300 bg-red-50 text-red-800'
          : 'border-amber-300 bg-amber-50 text-amber-800',
      ]"
      data-testid="preflight-banner"
      role="alert"
    >
      <div class="flex items-start justify-between gap-3">
        <span>{{ banner.message }}</span>
        <button
          type="button"
          class="shrink-0 rounded-md border border-current px-2 py-1 text-xs"
          :disabled="rechecking"
          data-testid="recheck-btn"
          @click="recheck"
        >
          {{ rechecking ? 'Re-checking…' : 'Re-detect' }}
        </button>
      </div>
    </div>

    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700"
          >Provider</label
        >
        <div class="mt-1 flex items-center gap-3">
          <select
            v-model="provider"
            data-testid="provider-select"
            class="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="auto">Auto-detect</option>
            <option value="claude">Claude CLI</option>
            <option value="codex">Codex CLI</option>
          </select>
          <span
            v-if="detectedBadge"
            :class="[
              'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium',
              detectedBadge.tone === 'ok'
                ? 'bg-emerald-100 text-emerald-800'
                : detectedBadge.tone === 'warning'
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-red-100 text-red-800',
            ]"
            data-testid="provider-badge"
          >
            {{ detectedBadge.label }}
          </span>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          "Auto-detect" uses whichever CLI is found on your PATH (claude preferred over codex).
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700"
          >Config directory (optional)</label
        >
        <input
          v-model="configDir"
          type="text"
          placeholder="~/.claude-personal"
          data-testid="config-dir-input"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <p class="mt-1 text-xs text-gray-500">
          Path passed to the CLI as <code>CLAUDE_CONFIG_DIR</code> /
          <code>CODEX_HOME</code>. Useful for sandboxed installs that share the
          binary but want a separate session/credential profile. Leave empty to
          use the CLI's default.
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Model</label>
        <select
          v-if="!useCustom"
          v-model="modelValue"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option v-for="opt in modelOptionsForProvider" :key="opt.id" :value="opt.id">
            {{ opt.label }}
          </option>
          <option value="__custom__" @click="useCustom = true">Custom…</option>
        </select>
        <div v-else class="mt-1 flex gap-2">
          <input
            v-model="customModel"
            type="text"
            placeholder="model-id"
            class="flex-1 rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="button"
            class="rounded-md border border-gray-300 px-3 py-2 text-sm"
            @click="useCustom = false"
          >
            Back to list
          </button>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          Shipped candidates come from the packaged <code>models.yaml</code>.
        </p>
      </div>

      <div class="flex justify-end">
        <button
          data-testid="save-llm"
          :disabled="saving"
          class="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          @click="save"
        >
          <span v-if="saving" class="inline-spinner" aria-hidden="true" />
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inline-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: inline-spin 0.8s linear infinite;
}
@keyframes inline-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .inline-spinner {
    animation: none;
    border-top-color: rgba(255, 255, 255, 0.85);
  }
}
</style>
