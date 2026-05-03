<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SettingsSidebar from '@/components/settings/SettingsSidebar.vue'
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import DatabaseSettings from '@/components/settings/DatabaseSettings.vue'
import PresetSettings from '@/components/settings/PresetSettings.vue'
import ReadingSettings from '@/components/settings/ReadingSettings.vue'
import BackupSettings from '@/components/settings/BackupSettings.vue'
import LlmSettings from '@/components/settings/LlmSettings.vue'
import SettingsTtsPanel from '@/components/settings/SettingsTtsPanel.vue'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()

const activeSection = computed(() => {
  return (route.params.section as string) || 'general'
})

function navigateToSection(section: string) {
  router.push(`/settings/${section}`)
}

onMounted(() => {
  settingsStore.fetchSettings()
})
</script>

<template>
  <div class="settings-page">
    <div class="settings-layout">
      <SettingsSidebar
        :active-section="activeSection"
        class="settings-sidebar"
        @select="navigateToSection"
      />
      <div class="settings-content">
        <GeneralSettings v-if="activeSection === 'general'" />
        <DatabaseSettings v-else-if="activeSection === 'database'" />
        <PresetSettings v-else-if="activeSection === 'presets'" />
        <ReadingSettings v-else-if="activeSection === 'reading'" />
        <BackupSettings v-else-if="activeSection === 'backup'" />
        <LlmSettings v-else-if="activeSection === 'llm'" />
        <SettingsTtsPanel v-else-if="activeSection === 'tts'" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-layout {
  display: flex;
  gap: 2rem;
}

.settings-sidebar {
  width: 220px;
  flex-shrink: 0;
}

.settings-content {
  flex: 1;
  min-width: 0;
}

@media (max-width: 767px) {
  .settings-layout {
    flex-direction: column;
    gap: 1rem;
  }

  .settings-sidebar {
    width: 100%;
  }
}
</style>
