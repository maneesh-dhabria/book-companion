<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { path: '/', label: 'Library', icon: '📚' },
  { path: '/concepts', label: 'Concepts', icon: '💡' },
  { path: '/search', label: 'Search', icon: '🔍' },
  { path: '/annotations', label: 'Notes', icon: '💬' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]
</script>

<template>
  <nav class="bottom-tab-bar" data-testid="bottom-tab-bar" role="navigation" aria-label="Main navigation">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="bottom-tab"
      data-testid="tab-item"
      :class="{ active: route.path === tab.path || (tab.path !== '/' && route.path.startsWith(tab.path)) }"
    >
      <span class="bottom-tab-icon">{{ tab.icon }}</span>
      <span class="bottom-tab-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.bottom-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  display: flex;
  background: var(--color-bg-primary);
  border-top: 1px solid var(--color-border);
  z-index: 50;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.bottom-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  text-decoration: none;
  color: var(--color-text-muted);
  min-height: 44px;
  transition: color 0.15s;
}

.bottom-tab.active {
  color: var(--color-accent);
}

.bottom-tab-icon {
  font-size: 20px;
}

.bottom-tab-label {
  font-size: 10px;
}
</style>
