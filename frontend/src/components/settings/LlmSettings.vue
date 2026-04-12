<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const saving = ref(false)

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
    await settingsStore.saveSettings({
      llm: {
        provider: provider.value,
        cli_command: cliCommand.value,
        config_dir: configDir.value || null,
      } as any,
    })
  } finally {
    saving.value = false
  }
}
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
