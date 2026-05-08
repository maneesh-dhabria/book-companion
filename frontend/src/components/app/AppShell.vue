<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'

import Playbar from '@/components/audio/Playbar.vue'
import KeyboardShortcutsOverlay from '@/components/app/KeyboardShortcutsOverlay.vue'
import CommandPalette from '@/components/search/CommandPalette.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import PersistentProcessingIndicator from '@/components/job/PersistentProcessingIndicator.vue'
import { initCacheSubscription } from '@/composables/audio/preloadCache'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

import BottomTabBar from './BottomTabBar.vue'
import IconRail from './IconRail.vue'
import TopBar from './TopBar.vue'

const { isMobile } = useBreakpoint()
const ttsPlayer = useTtsPlayerStore()

// FR-C10 — when the global Playbar is mounted (TTS active), expose its
// height as a CSS custom property so floating affordances (e.g. the
// BackToTopFab) can offset above it.
const shellStyle = computed(() => ({
  '--playbar-height': ttsPlayer.isActive ? '84px' : '0px',
}))

// FR-13 / FR-14 / D19 (spec): a single global Space-toggle handler.
// ReadingArea no longer owns Space (T10 deletes its branch).
function onGlobalKeydown(e: KeyboardEvent): void {
  if (e.key !== ' ') return
  if (!ttsPlayer.isActive) return
  const t = e.target as HTMLElement | null
  if (!t) return
  const tag = t.tagName
  const role = t.getAttribute('role')
  if (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'BUTTON' ||
    tag === 'A' ||
    tag === 'SELECT' ||
    role === 'button' ||
    t.isContentEditable
  ) {
    return
  }
  e.preventDefault()
  if (ttsPlayer.status === 'playing') ttsPlayer.pause()
  else ttsPlayer.play()
}

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
  initCacheSubscription()
})
onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKeydown)
})
</script>

<template>
  <div class="app-shell" :class="{ mobile: isMobile }" :style="shellStyle">
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
    <Playbar />
    <KeyboardShortcutsOverlay />
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
