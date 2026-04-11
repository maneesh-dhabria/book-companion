<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import QRCodeVue from 'qrcode.vue'

const store = useSettingsStore()

const allowLan = computed({
  get: () => store.settings?.network.allow_lan ?? false,
  set: (val: boolean) => {
    store.saveSettings({ network: { allow_lan: val } } as any)
  },
})

const showCostEstimates = computed({
  get: () => store.settings?.web.show_cost_estimates ?? false,
  set: (val: boolean) => {
    store.saveSettings({ web: { show_cost_estimates: val } } as any)
  },
})

const lanUrl = computed(() => {
  if (!store.settings?.network.allow_lan) return null
  const host = store.settings.network.host === '0.0.0.0' ? getLocalIp() : store.settings.network.host
  return `http://${host}:${store.settings.network.port}`
})

function getLocalIp(): string {
  // In the browser we can't detect local IP; show placeholder or use the host from settings
  return store.settings?.network.host === '0.0.0.0'
    ? window.location.hostname
    : store.settings?.network.host ?? 'localhost'
}
</script>

<template>
  <div class="general-settings">
    <h2 class="section-title">General</h2>

    <!-- LAN Access -->
    <div class="setting-group">
      <h3 class="group-title">Network Access</h3>
      <label class="toggle-row" data-testid="lan-toggle">
        <span class="toggle-label">
          <strong>Read on your phone</strong>
          <span class="toggle-description">Allow access from other devices on your local network</span>
        </span>
        <input
          v-model="allowLan"
          type="checkbox"
          class="toggle-input"
        />
      </label>

      <div v-if="allowLan && lanUrl" class="lan-info">
        <p class="lan-url" data-testid="lan-url">{{ lanUrl }}</p>
        <div class="qr-container" data-testid="lan-qr-code">
          <QRCodeVue :value="lanUrl" :size="160" />
        </div>
      </div>
    </div>

    <!-- Cost Estimates -->
    <div class="setting-group">
      <h3 class="group-title">Display</h3>
      <label class="toggle-row">
        <span class="toggle-label">
          <strong>Show cost estimates</strong>
          <span class="toggle-description">Display LLM usage cost estimates in the UI</span>
        </span>
        <input
          v-model="showCostEstimates"
          type="checkbox"
          class="toggle-input"
        />
      </label>
    </div>

    <!-- LLM Info (read-only) -->
    <div v-if="store.settings" class="setting-group">
      <h3 class="group-title">LLM Configuration</h3>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Provider</span>
          <span class="info-value">{{ store.settings.llm.provider }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Model</span>
          <span class="info-value">{{ store.settings.llm.model }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Timeout</span>
          <span class="info-value">{{ store.settings.llm.timeout_seconds }}s</span>
        </div>
        <div class="info-item">
          <span class="info-label">Max retries</span>
          <span class="info-value">{{ store.settings.llm.max_retries }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Budget limit</span>
          <span class="info-value">${{ store.settings.llm.max_budget_usd }}</span>
        </div>
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

.setting-group {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.group-title {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #888);
  margin-bottom: 0.75rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0;
  cursor: pointer;
}

.toggle-label {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.toggle-description {
  font-size: 0.8125rem;
  color: var(--color-text-muted, #888);
}

.toggle-input {
  width: 2.5rem;
  height: 1.25rem;
  appearance: none;
  background: var(--color-bg-muted, #ddd);
  border-radius: 0.625rem;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-input:checked {
  background: var(--color-accent, #2563eb);
}

.toggle-input::before {
  content: '';
  position: absolute;
  width: 1rem;
  height: 1rem;
  background: white;
  border-radius: 50%;
  top: 0.125rem;
  left: 0.125rem;
  transition: transform 0.2s;
}

.toggle-input:checked::before {
  transform: translateX(1.25rem);
}

.lan-info {
  margin-top: 0.75rem;
  padding: 1rem;
  background: var(--color-bg-muted, #f9fafb);
  border-radius: 0.5rem;
}

.lan-url {
  font-family: monospace;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.qr-container {
  display: flex;
  justify-content: center;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.info-label {
  font-size: 0.75rem;
  color: var(--color-text-muted, #888);
}

.info-value {
  font-size: 0.875rem;
  font-weight: 500;
}
</style>
