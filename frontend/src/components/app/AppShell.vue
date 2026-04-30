<script setup lang="ts">
import CommandPalette from '@/components/search/CommandPalette.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import PersistentProcessingIndicator from '@/components/job/PersistentProcessingIndicator.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import BottomTabBar from './BottomTabBar.vue'
import IconRail from './IconRail.vue'
import TopBar from './TopBar.vue'

const { isMobile } = useBreakpoint()
</script>

<template>
  <div class="app-shell" :class="{ mobile: isMobile }">
    <IconRail v-if="!isMobile" data-testid="icon-rail-sidebar" />
    <div class="app-main" :class="{ 'with-rail': !isMobile }">
      <TopBar />
      <main class="app-content">
        <slot />
      </main>
    </div>
    <BottomTabBar v-if="isMobile" />
    <CommandPalette />
    <ToastContainer />
    <PersistentProcessingIndicator />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-main {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-main.with-rail {
  margin-left: 56px;
}

.app-content {
  flex: 1;
  overflow-y: auto;
}

.app-shell.mobile .app-content {
  padding-bottom: 56px;
}
</style>
