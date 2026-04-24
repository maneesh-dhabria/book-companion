<script setup lang="ts">
import { computed, onMounted, ref, watchEffect } from 'vue'
import { useSettingsStore } from '@/stores/settings'

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
const modelsPayload = ref<ModelsPayload | null>(null)
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

const cliCommand = computed({
  get: () => settingsStore.settings?.llm?.cli_command ?? '',
  set: (val: string) => {
    if (settingsStore.settings?.llm) {
      settingsStore.settings.llm.cli_command = val
    }
  },
})

const configDir = computed({
  get: () => settingsStore.settings?.llm?.config_dir ?? '',
  set: (val: string) => {
    if (settingsStore.settings?.llm) {
      settingsStore.settings.llm.config_dir = val || null
    }
  },
})

async function save() {
  saving.value = true
  try {
    const effectiveModel = useCustom.value ? customModel.value.trim() : modelValue.value
    await settingsStore.saveSettings({
      llm: {
        provider: provider.value,
        cli_command: cliCommand.value,
        config_dir: configDir.value || null,
        ...(effectiveModel ? { model: effectiveModel } : {}),
      } as any,
    })
  } finally {
    saving.value = false
  }
}

// T31 / FR-F1.2 — pull the shipped models.yaml candidates + auto-detected
// provider from /api/v1/config/models, populate the dropdown, and
// preselect the currently-configured model.
const modelOptionsForProvider = computed<ModelOption[]>(() => {
  if (!modelsPayload.value) return []
  const prov = provider.value === 'auto'
    ? (modelsPayload.value.detected_provider || 'claude')
    : provider.value
  return modelsPayload.value.providers[prov] || []
})

watchEffect(() => {
  // When the provider changes, reset modelValue to the first option if the
  // current value isn't in the new provider's list. Custom stays sticky.
  if (useCustom.value) return
  const opts = modelOptionsForProvider.value
  if (!opts.length) return
  if (!opts.some((o) => o.id === modelValue.value)) {
    modelValue.value = opts[0].id
  }
})

onMounted(async () => {
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
      <h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">LLM Provider</h3>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Configure which AI coding assistant CLI to use for summarization and evaluation.
      </p>
    </div>

    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Provider</label>
        <select
          v-model="provider"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        >
          <option value="auto">Auto-detect</option>
          <option value="claude">Claude CLI</option>
          <option value="codex">Codex CLI</option>
        </select>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          "Auto-detect" will use whichever CLI is found on your PATH (claude preferred over codex).
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >CLI Command (optional)</label
        >
        <input
          v-model="cliCommand"
          type="text"
          placeholder="claude"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Override the CLI command path. Leave empty to use the default from PATH.
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Model</label>
        <select
          v-if="!useCustom"
          v-model="modelValue"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        >
          <option
            v-for="opt in modelOptionsForProvider"
            :key="opt.id"
            :value="opt.id"
          >
            {{ opt.label }}
          </option>
          <option value="__custom__" @click="useCustom = true">Custom…</option>
        </select>
        <div v-else class="mt-1 flex gap-2">
          <input
            v-model="customModel"
            type="text"
            placeholder="model-id"
            class="flex-1 rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          />
          <button
            type="button"
            class="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600"
            @click="useCustom = false"
          >
            Back to list
          </button>
        </div>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Changes apply after the server is restarted. Shipped candidates come
          from the packaged <code>models.yaml</code>.
        </p>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >Config Directory (optional)</label
        >
        <input
          v-model="configDir"
          type="text"
          placeholder="~/.claude"
          class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Override the CLI config directory (e.g., for using a separate Claude profile).
        </p>
      </div>

      <div class="flex justify-end">
        <button
          @click="save"
          :disabled="saving"
          class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>
