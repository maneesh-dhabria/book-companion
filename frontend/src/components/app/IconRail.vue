<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/', label: 'Library', icon: '📚' },
  { path: '/concepts', label: 'Concepts', icon: '💡' },
  { path: '/annotations', label: 'Annotations', icon: '💬' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]
</script>

<template>
  <nav class="icon-rail" role="navigation" aria-label="Main navigation">
    <router-link to="/" class="icon-rail-logo" aria-label="Book Companion home">
      <span class="text-lg font-bold">BC</span>
    </router-link>
    <div class="icon-rail-items">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="icon-rail-item"
        :class="{ active: route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)) }"
        :title="item.label"
      >
        <span class="icon-rail-icon">{{ item.icon }}</span>
        <span class="icon-rail-label">{{ item.label }}</span>
      </router-link>
    </div>
  </nav>
</template>

<style scoped>
.icon-rail {
  width: 56px;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  background: var(--color-sidebar-bg);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  z-index: 50;
}

.icon-rail-logo {
  color: var(--color-sidebar-text);
  margin-bottom: 24px;
  opacity: 0.8;
  text-decoration: none;
  cursor: pointer;
  display: inline-block;
  border-radius: 6px;
  padding: 2px 6px;
}
.icon-rail-logo:hover {
  opacity: 1;
}
.icon-rail-logo:focus-visible {
  outline: 2px solid var(--color-accent, #4f46e5);
  outline-offset: 2px;
}

.icon-rail-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.icon-rail-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--color-sidebar-text);
  opacity: 0.7;
  transition: all 0.15s ease;
  cursor: pointer;
}

.icon-rail-item:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

.icon-rail-item.active {
  opacity: 1;
  background: var(--color-sidebar-active);
  color: #fff;
}

.icon-rail-icon {
  font-size: 20px;
  line-height: 1;
}

.icon-rail-label {
  font-size: 9px;
  margin-top: 2px;
  text-align: center;
}
</style>
