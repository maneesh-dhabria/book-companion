<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  defaultTab?: 'annotations' | 'ai'
}>()

const emit = defineEmits<{
  close: []
}>()

const activeTab = ref<'annotations' | 'ai'>(props.defaultTab ?? 'annotations')
// D2 — parent passes `defaultTab='ai'` when the user hits Ask AI; update
// if the prop changes after mount so the tab flips without a remount.
watch(
  () => props.defaultTab,
  (v) => {
    if (v) activeTab.value = v
  },
)
</script>

<template>
  <aside v-if="open" class="context-sidebar">
    <div class="sidebar-header">
      <div class="tab-bar">
        <button
          class="tab"
          :class="{ active: activeTab === 'annotations' }"
          @click="activeTab = 'annotations'"
        >
          Annotations
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'ai' }"
          @click="activeTab = 'ai'"
        >
          AI Chat
        </button>
      </div>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>

    <div class="sidebar-content">
      <slot :name="activeTab" />
    </div>
  </aside>
</template>

<style scoped>
.context-sidebar { width: 360px; min-width: 360px; border-left: 1px solid var(--reader-border, var(--color-border, #e0e0e0)); background: var(--reader-bg, var(--color-bg-primary, #fff)); display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.sidebar-header { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--reader-border, var(--color-border, #e0e0e0)); }
.tab-bar { display: flex; gap: 0; }
.tab { padding: 0.5rem 0.75rem; border: none; background: none; cursor: pointer; font-size: 0.8rem; font-weight: 500; color: var(--reader-text-secondary, var(--color-text-secondary, #666)); border-bottom: 2px solid transparent; }
.tab.active { color: var(--color-primary, #3b82f6); border-bottom-color: var(--color-primary, #3b82f6); }
.close-btn { background: none; border: none; font-size: 1.25rem; cursor: pointer; color: var(--reader-text-secondary, var(--color-text-secondary, #666)); }
.sidebar-content { flex: 1; overflow-y: auto; }
</style>
