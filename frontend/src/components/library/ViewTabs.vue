<script setup lang="ts">
import { useBooksStore } from '@/stores/books'
import { ref } from 'vue'

const store = useBooksStore()
const newViewName = ref('')
const showNewInput = ref(false)

function createView() {
  if (!newViewName.value.trim()) return
  store.createViewFromCurrent(newViewName.value.trim())
  newViewName.value = ''
  showNewInput.value = false
}
</script>

<template>
  <div class="view-tabs">
    <button
      v-for="view in store.views"
      :key="view.id"
      class="view-tab"
      :class="{ active: store.currentViewId === view.id }"
      @click="store.switchView(view.id)"
    >
      {{ view.name }}
    </button>
    <button
      v-if="!showNewInput"
      class="view-tab new-view"
      @click="showNewInput = true"
    >
      + New View
    </button>
    <div v-else class="new-view-input">
      <input
        v-model="newViewName"
        placeholder="View name"
        class="view-name-input"
        @keyup.enter="createView"
        @keyup.escape="showNewInput = false"
      />
      <button class="save-btn" @click="createView">Save</button>
    </div>
  </div>
</template>

<style scoped>
.view-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
}

.view-tab {
  padding: 6px 14px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
  white-space: nowrap;
  transition: all 0.1s;
}

.view-tab:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
}

.view-tab.active {
  background: var(--color-accent);
  color: #fff;
}

.view-tab.new-view {
  color: var(--color-text-muted);
}

.new-view-input {
  display: flex;
  align-items: center;
  gap: 4px;
}

.view-name-input {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  width: 120px;
}

.save-btn {
  height: 28px;
  padding: 0 8px;
  border: none;
  background: var(--color-accent);
  color: #fff;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
</style>
