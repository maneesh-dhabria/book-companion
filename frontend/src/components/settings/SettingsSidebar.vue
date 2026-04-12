<script setup lang="ts">
defineProps<{
  activeSection: string
}>()

const emit = defineEmits<{
  select: [section: string]
}>()

const sections = [
  { id: 'general', label: 'General', icon: '⚙' },
  { id: 'database', label: 'Database', icon: '🗄' },
  { id: 'presets', label: 'Presets', icon: '📋' },
  { id: 'reading', label: 'Reading', icon: '📖' },
  { id: 'backup', label: 'Backup & Export', icon: '💾' },
  { id: 'llm', label: 'LLM Provider', icon: '🤖' },
]
</script>

<template>
  <nav class="settings-nav" role="navigation" aria-label="Settings sections">
    <h2 class="settings-nav-title">Settings</h2>
    <ul class="settings-nav-list">
      <li
        v-for="section in sections"
        :key="section.id"
        class="settings-nav-item"
        :class="{ active: activeSection === section.id }"
        @click="emit('select', section.id)"
      >
        <span class="nav-icon">{{ section.icon }}</span>
        <span class="nav-label">{{ section.label }}</span>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.settings-nav-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #888);
  margin-bottom: 0.5rem;
  padding: 0 0.75rem;
}

.settings-nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.settings-nav-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--color-text, #333);
  transition: background-color 0.15s;
}

.settings-nav-item:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.05));
}

.settings-nav-item.active {
  background: var(--color-bg-active, rgba(0, 0, 0, 0.08));
  font-weight: 600;
  color: var(--color-accent, #2563eb);
}

.nav-icon {
  font-size: 1rem;
  width: 1.25rem;
  text-align: center;
}

.nav-label {
  flex: 1;
}

@media (max-width: 767px) {
  .settings-nav-list {
    display: flex;
    overflow-x: auto;
    gap: 0.25rem;
    padding-bottom: 0.5rem;
  }

  .settings-nav-item {
    white-space: nowrap;
    flex-shrink: 0;
  }
}
</style>
