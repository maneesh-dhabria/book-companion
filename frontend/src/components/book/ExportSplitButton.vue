<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    disabledReason?: string
    loading?: boolean
  }>(),
  { disabled: false, disabledReason: '', loading: false },
)

const emit = defineEmits<{
  download: []
  copy: []
}>()

const open = ref(false)
const chevronRef = ref<HTMLButtonElement | null>(null)
const menuRef = ref<HTMLUListElement | null>(null)

function onBodyClick() {
  if (props.disabled) return
  emit('download')
}

function openMenu() {
  if (props.disabled) return
  open.value = true
  nextTick(() => {
    const items = menuRef.value?.querySelectorAll<HTMLElement>('[role="menuitem"]')
    items?.[0]?.focus()
    document.addEventListener('click', onDocClick, { capture: true })
  })
}

function closeMenu(restoreFocus = true) {
  if (!open.value) return
  open.value = false
  document.removeEventListener('click', onDocClick, { capture: true })
  if (restoreFocus) {
    nextTick(() => chevronRef.value?.focus())
  }
}

function toggleMenu() {
  if (open.value) closeMenu()
  else openMenu()
}

function onDocClick(e: MouseEvent) {
  const t = e.target as Node | null
  if (!t) return
  if (chevronRef.value?.contains(t)) return
  if (menuRef.value?.contains(t)) return
  closeMenu(false)
}

function onCopyClick() {
  emit('copy')
  closeMenu()
}

function onDownloadMenuItem() {
  closeMenu()
  emit('download')
}

function onMenuKeydown(e: KeyboardEvent) {
  const items = Array.from(
    menuRef.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
  )
  const active = document.activeElement as HTMLElement | null
  const idx = active ? items.indexOf(active) : -1

  if (e.key === 'Escape') {
    e.preventDefault()
    closeMenu()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    items[(idx + 1) % items.length]?.focus()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    items[(idx - 1 + items.length) % items.length]?.focus()
  } else if (e.key === 'Home') {
    e.preventDefault()
    items[0]?.focus()
  } else if (e.key === 'End') {
    e.preventDefault()
    items[items.length - 1]?.focus()
  } else if (e.key === 'Tab') {
    closeMenu(false)
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, { capture: true })
})
</script>

<template>
  <div class="export-split" role="group">
    <button
      type="button"
      class="split-body"
      data-role="body"
      :aria-disabled="disabled || undefined"
      :disabled="disabled"
      :title="disabled ? disabledReason : ''"
      @click="onBodyClick"
    >
      <span v-if="loading" class="spinner" aria-hidden="true"></span>
      <span>Export Markdown</span>
    </button>
    <button
      ref="chevronRef"
      type="button"
      class="split-chevron"
      data-role="chevron"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-disabled="disabled || undefined"
      :disabled="disabled"
      :title="disabled ? disabledReason : ''"
      @click="toggleMenu"
    >
      <span aria-hidden="true">▾</span>
    </button>
    <ul
      v-if="open"
      ref="menuRef"
      class="split-menu"
      role="menu"
      tabindex="-1"
      @keydown="onMenuKeydown"
    >
      <li role="menuitem" tabindex="0" @click="onDownloadMenuItem">
        Download Markdown
      </li>
      <li role="menuitem" tabindex="0" @click="onCopyClick">
        Copy to Clipboard
      </li>
    </ul>
  </div>
</template>

<style scoped>
.export-split {
  position: relative;
  display: inline-flex;
}
.split-body,
.split-chevron {
  background: var(--color-accent);
  color: #fff;
  border: 1px solid var(--color-accent);
  padding: 6px 14px;
  font-size: 14px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.split-body {
  border-radius: 6px 0 0 6px;
}
.split-chevron {
  border-left-color: rgba(255, 255, 255, 0.3);
  border-radius: 0 6px 6px 0;
  padding: 6px 8px;
}
.split-body[disabled],
.split-chevron[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}
.split-body:not([disabled]):hover,
.split-chevron:not([disabled]):hover {
  background: var(--color-accent-hover);
}
.split-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  margin: 0;
  padding: 4px 0;
  min-width: 200px;
  list-style: none;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 20;
  outline: none;
}
.split-menu li {
  padding: 8px 14px;
  cursor: pointer;
  color: var(--color-text-primary);
  font-size: 14px;
}
.split-menu li:hover,
.split-menu li:focus {
  background: var(--color-bg-tertiary);
  outline: none;
}
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
