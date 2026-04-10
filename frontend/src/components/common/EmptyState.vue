<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
  actionTo?: string
}>()
</script>

<template>
  <div class="empty-state">
    <div v-if="icon" class="empty-state-icon">{{ icon }}</div>
    <h3 class="empty-state-title">{{ title }}</h3>
    <p v-if="description" class="empty-state-description">{{ description }}</p>
    <router-link v-if="actionLabel && actionTo" :to="actionTo" class="empty-state-action">
      {{ actionLabel }}
    </router-link>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  text-align: center;
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 8px;
}

.empty-state-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 24px;
  max-width: 400px;
}

.empty-state-action {
  display: inline-flex;
  align-items: center;
  padding: 8px 20px;
  background: var(--color-accent);
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: background 0.15s;
}

.empty-state-action:hover {
  background: var(--color-accent-hover);
}
</style>
