<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { RouterLink } from 'vue-router'

defineProps<{
  editRoute: { name: string; params: Record<string, string> }
}>()

const emit = defineEmits<{
  'open-reader-settings': []
}>()

const open = ref(false)
const triggerRef = ref<HTMLButtonElement | null>(null)
const menuRef = ref<HTMLUListElement | null>(null)

function openMenu() {
  open.value = true
  nextTick(() => {
    const first = menuRef.value?.querySelector<HTMLElement>('[role="menuitem"]')
    first?.focus()
    document.addEventListener('click', onDocClick, { capture: true })
  })
}

function closeMenu(restoreFocus = true) {
  if (!open.value) return
  open.value = false
  document.removeEventListener('click', onDocClick, { capture: true })
  if (restoreFocus) nextTick(() => triggerRef.value?.focus())
}

function toggle() {
  if (open.value) closeMenu()
  else openMenu()
}

function onDocClick(e: MouseEvent) {
  const t = e.target as Node | null
  if (!t) return
  if (triggerRef.value?.contains(t)) return
  if (menuRef.value?.contains(t)) return
  closeMenu(false)
}

function onCustomize() {
  emit('open-reader-settings')
  closeMenu()
}

function onMenuKeydown(e: KeyboardEvent) {
  const items = Array.from(
    menuRef.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
  )
  const idx = items.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'Escape') {
    e.preventDefault()
    closeMenu()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    items[(idx + 1) % items.length]?.focus()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    items[(idx - 1 + items.length) % items.length]?.focus()
  } else if (e.key === 'Tab') {
    closeMenu(false)
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, { capture: true })
})
</script>

<template>
  <div class="overflow-menu">
    <button
      ref="triggerRef"
      type="button"
      class="overflow-trigger"
      aria-haspopup="menu"
      :aria-expanded="open"
      aria-label="More actions"
      @click="toggle"
    >
      <span aria-hidden="true">⋯</span>
    </button>
    <ul
      v-if="open"
      ref="menuRef"
      class="overflow-popover"
      role="menu"
      tabindex="-1"
      @keydown="onMenuKeydown"
    >
      <li role="none">
        <RouterLink
          :to="editRoute"
          role="menuitem"
          tabindex="0"
          class="overflow-item"
          @click="closeMenu(false)"
          >Edit Structure</RouterLink
        >
      </li>
      <li
        role="menuitem"
        tabindex="0"
        class="overflow-item"
        @click="onCustomize"
      >
        Customize Reader
      </li>
    </ul>
  </div>
</template>

<style scoped>
.overflow-menu {
  position: relative;
  display: inline-block;
}
.overflow-trigger {
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  color: var(--color-text-primary);
}
.overflow-trigger:hover {
  background: var(--color-bg-tertiary);
}
.overflow-popover {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  margin: 0;
  padding: 4px 0;
  min-width: 180px;
  list-style: none;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 20;
  outline: none;
}
.overflow-item {
  display: block;
  padding: 8px 14px;
  cursor: pointer;
  color: var(--color-text-primary);
  font-size: 14px;
  text-decoration: none;
}
.overflow-item:hover,
.overflow-item:focus {
  background: var(--color-bg-tertiary);
  outline: none;
}
</style>
