<script setup lang="ts">
defineProps<{
  type?: 'card' | 'list-item' | 'table-row' | 'text'
  count?: number
}>()
</script>

<template>
  <div class="skeleton-container">
    <template v-for="i in (count || 1)" :key="i">
      <div v-if="type === 'card'" class="skeleton skeleton-card">
        <div class="skeleton-cover" />
        <div class="skeleton-line w-3/4" />
        <div class="skeleton-line w-1/2" />
      </div>
      <div v-else-if="type === 'list-item'" class="skeleton skeleton-list-item">
        <div class="skeleton-avatar" />
        <div class="skeleton-text">
          <div class="skeleton-line w-3/4" />
          <div class="skeleton-line w-1/2" />
        </div>
      </div>
      <div v-else-if="type === 'table-row'" class="skeleton skeleton-table-row">
        <div class="skeleton-line" v-for="j in 5" :key="j" />
      </div>
      <div v-else class="skeleton">
        <div class="skeleton-line" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-card {
  padding: 16px;
  border-radius: 8px;
  background: var(--color-bg-secondary);
}

.skeleton-cover {
  width: 100%;
  height: 180px;
  border-radius: 4px;
  background: var(--color-bg-tertiary);
  margin-bottom: 12px;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: var(--color-bg-tertiary);
  margin-bottom: 8px;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.skeleton-avatar {
  width: 40px;
  height: 56px;
  border-radius: 4px;
  background: var(--color-bg-tertiary);
  flex-shrink: 0;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-text {
  flex: 1;
}

.skeleton-table-row {
  display: flex;
  gap: 16px;
  padding: 8px 0;
}

.skeleton-table-row .skeleton-line {
  flex: 1;
}

.w-3\/4 { width: 75%; }
.w-1\/2 { width: 50%; }

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
</style>
