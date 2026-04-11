<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const store = useSettingsStore()

onMounted(() => {
  store.fetchDatabaseStats()
  store.fetchMigrationStatus()
})
</script>

<template>
  <div class="database-settings">
    <h2 class="section-title">Database</h2>

    <!-- Connection Info -->
    <div class="setting-group">
      <h3 class="group-title">Connection</h3>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Host</span>
          <span class="info-value">{{ store.settings?.network.host ?? 'localhost' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Port</span>
          <span class="info-value">{{ store.settings?.network.port ?? 5438 }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Password</span>
          <span class="info-value">••••••••</span>
        </div>
      </div>
    </div>

    <!-- Migration Status -->
    <div class="setting-group">
      <h3 class="group-title">Migrations</h3>
      <div v-if="store.migrationStatus" class="migration-status">
        <div class="status-row">
          <span class="status-label">Status</span>
          <span
            class="status-badge"
            :class="store.migrationStatus.is_behind ? 'behind' : 'current'"
            data-testid="migration-status"
          >
            {{ store.migrationStatus.is_behind ? 'Behind' : 'Up to date' }}
          </span>
        </div>
        <div v-if="store.migrationStatus.current" class="status-row">
          <span class="status-label">Current revision</span>
          <code class="status-value">{{ store.migrationStatus.current }}</code>
        </div>
        <button
          v-if="store.migrationStatus.is_behind"
          class="btn-primary"
          data-testid="run-migrations-btn"
          @click="store.triggerMigrations()"
        >
          Run Migrations
        </button>
      </div>
      <div v-else class="loading-text">Loading migration status...</div>
    </div>

    <!-- Table Row Counts -->
    <div class="setting-group">
      <h3 class="group-title">Table Statistics</h3>
      <div v-if="store.dbStats" class="stats-table">
        <div
          v-for="(count, table) in store.dbStats"
          :key="table"
          class="stat-row"
          :data-testid="`db-stat-${table}`"
        >
          <span class="stat-table">{{ formatTableName(table as string) }}</span>
          <span class="stat-count">{{ count.toLocaleString() }}</span>
        </div>
      </div>
      <div v-else class="loading-text">Loading database stats...</div>
    </div>
  </div>
</template>

<script lang="ts">
function formatTableName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

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

.migration-status {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-label {
  font-size: 0.875rem;
  color: var(--color-text-muted, #888);
  min-width: 120px;
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 1rem;
}

.status-badge.current {
  background: #dcfce7;
  color: #166534;
}

.status-badge.behind {
  background: #fef3c7;
  color: #92400e;
}

.status-value {
  font-size: 0.8125rem;
}

.stats-table {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
}

.stat-row:nth-child(even) {
  background: var(--color-bg-muted, #f9fafb);
}

.stat-table {
  font-size: 0.875rem;
}

.stat-count {
  font-size: 0.875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.loading-text {
  font-size: 0.875rem;
  color: var(--color-text-muted, #888);
}

.btn-primary {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--color-accent, #2563eb);
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  width: fit-content;
}

.btn-primary:hover {
  opacity: 0.9;
}
</style>
