<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string
  options: string[]
  id?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const activeIndex = ref(0)
const triggerRef = ref<HTMLButtonElement | null>(null)
const listboxRef = ref<HTMLUListElement | null>(null)

const FALLBACKS: Record<string, string> = {
  Georgia: "Georgia, 'Lora', 'Merriweather', serif",
  Inter: "'Inter', system-ui, -apple-system, sans-serif",
  Merriweather: "'Merriweather', 'Lora', Georgia, serif",
  'Fira Code': "'Fira Code', 'Source Code Pro', ui-monospace, monospace",
  Lora: "'Lora', 'Merriweather', Georgia, serif",
  'Source Serif Pro': "'Source Serif Pro', 'Lora', 'Merriweather', serif",
}

function familyFor(name: string): string {
  return FALLBACKS[name] ?? name
}

function optionId(name: string): string {
  return `font-opt-${name.toLowerCase().replace(/\s+/g, '-')}`
}

const activeId = computed(() => {
  const o = props.options[activeIndex.value]
  return o ? optionId(o) : undefined
})

watch(
  () => props.modelValue,
  (v) => {
    const idx = props.options.indexOf(v)
    if (idx >= 0) activeIndex.value = idx
  },
  { immediate: true },
)

function openMenu() {
  open.value = true
  const idx = props.options.indexOf(props.modelValue)
  activeIndex.value = idx >= 0 ? idx : 0
  nextTick(() => {
    listboxRef.value?.focus()
    document.addEventListener('click', onDocClick, { capture: true })
  })
}

function closeMenu(restoreFocus = true) {
  if (!open.value) return
  open.value = false
  document.removeEventListener('click', onDocClick, { capture: true })
  if (restoreFocus) {
    nextTick(() => triggerRef.value?.focus())
  }
}

function onDocClick(e: MouseEvent) {
  const t = e.target as Node | null
  if (!t) return
  if (triggerRef.value?.contains(t)) return
  if (listboxRef.value?.contains(t)) return
  closeMenu(false)
}

function selectIndex(idx: number) {
  const v = props.options[idx]
  if (v === undefined) return
  emit('update:modelValue', v)
  closeMenu()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % props.options.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value =
      (activeIndex.value - 1 + props.options.length) % props.options.length
  } else if (e.key === 'Home') {
    e.preventDefault()
    activeIndex.value = 0
  } else if (e.key === 'End') {
    e.preventDefault()
    activeIndex.value = props.options.length - 1
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    selectIndex(activeIndex.value)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closeMenu()
  } else if (e.key === 'Tab') {
    closeMenu(false)
  }
}

function onTriggerKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    openMenu()
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, { capture: true })
})
</script>

<template>
  <div class="font-listbox">
    <button
      ref="triggerRef"
      type="button"
      class="setting-select font-trigger"
      :aria-haspopup="'listbox'"
      :aria-expanded="open"
      :id="id"
      @click="open ? closeMenu() : openMenu()"
      @keydown="onTriggerKeydown"
    >
      <span :style="{ fontFamily: familyFor(modelValue) }">{{ modelValue }}</span>
      <span class="font-trigger-chevron" aria-hidden="true">▾</span>
    </button>
    <ul
      v-if="open"
      ref="listboxRef"
      class="font-listbox-popover"
      role="listbox"
      tabindex="-1"
      :aria-activedescendant="activeId"
      @keydown="onKeydown"
    >
      <li
        v-for="(opt, idx) in options"
        :key="opt"
        :id="optionId(opt)"
        role="option"
        :aria-selected="opt === modelValue"
        :class="{ active: idx === activeIndex }"
        :style="{ fontFamily: familyFor(opt) }"
        @click="selectIndex(idx)"
        @mouseenter="activeIndex = idx"
      >
        {{ opt }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.font-listbox {
  position: relative;
  display: inline-block;
  width: 100%;
}
.font-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  text-align: left;
  cursor: pointer;
}
.font-trigger-chevron {
  opacity: 0.7;
  font-size: 0.85em;
}
.font-listbox-popover {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  z-index: 10;
  max-height: 240px;
  overflow-y: auto;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  outline: none;
}
.font-listbox-popover li {
  padding: 6px 12px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-primary);
}
.font-listbox-popover li.active,
.font-listbox-popover li:hover {
  background: var(--color-bg-tertiary);
}
.font-listbox-popover li[aria-selected='true'] {
  font-weight: 600;
}
</style>
