<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import ThemeCard from './ThemeCard.vue'
import { themeMap } from './themeColors'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const store = useReaderSettingsStore()

const NAME_ORDER = ['Light', 'Dark', 'Sepia', 'Night', 'Paper', 'High Contrast']
function rank(name: string) {
  const i = NAME_ORDER.indexOf(name)
  return i === -1 ? 999 : i
}

interface Card {
  key: string
  label: string
  bg: string
  fg: string
  type: 'system' | 'custom'
  presetId?: number
  empty?: boolean
}

const systemCards = computed<Card[]>(() =>
  [...store.presets]
    .sort((a, b) => rank(a.name) - rank(b.name))
    .map((p) => {
      const c = themeMap[p.theme] ?? themeMap.light
      return { key: `system:${p.id}`, label: p.name, bg: c.bg, fg: c.fg, presetId: p.id, type: 'system' as const }
    }),
)

const customCard = computed<Card>(() => ({
  key: 'custom',
  label: 'Custom',
  bg: store.customTheme?.bg ?? '#ffffff',
  fg: store.customTheme?.fg ?? '#1f2937',
  type: 'custom' as const,
  empty: !store.customTheme,
}))

const cards = computed<Card[]>(() => [...systemCards.value, customCard.value])

const activeIndex = computed(() =>
  cards.value.findIndex((c) => c.key === store.appliedPresetKey),
)

const focusedIndex = ref(activeIndex.value >= 0 ? activeIndex.value : 0)

const cardEls = ref<Array<HTMLElement | null>>([])
function setCardRef(idx: number, el: unknown) {
  if (!el || typeof el !== 'object') {
    cardEls.value[idx] = null
    return
  }
  const obj = el as { $el?: unknown; tagName?: string }
  const node = obj.tagName ? (obj as unknown as HTMLElement) : (obj.$el as HTMLElement | undefined) ?? null
  cardEls.value[idx] = node ?? null
}

const emptyCellCount = computed(() => {
  const n = cards.value.length
  const remainder = n % 3
  return remainder === 0 ? 0 : 3 - remainder
})

function focusIndex(i: number) {
  focusedIndex.value = i
  nextTick(() => {
    cardEls.value[i]?.focus?.()
  })
}

function onCardClick(idx: number) {
  const c = cards.value[idx]
  focusedIndex.value = idx
  if (c.type === 'system' && c.presetId !== undefined) {
    store.applyPreset(c.presetId)
  } else {
    if (store.appliedPresetKey !== 'custom') store.applyCustom()
    store.toggleCustomEditor()
  }
}

function onCardKeydown(e: KeyboardEvent, idx: number) {
  const n = cards.value.length
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    e.preventDefault()
    focusIndex((idx + 1) % n)
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    e.preventDefault()
    focusIndex((idx - 1 + n) % n)
  } else if (e.key === 'Home') {
    e.preventDefault()
    focusIndex(0)
  } else if (e.key === 'End') {
    e.preventDefault()
    focusIndex(n - 1)
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    onCardClick(idx)
  }
}

function isActive(c: Card): boolean {
  return c.key === store.appliedPresetKey
}

function focusActiveCard() {
  const i = activeIndex.value >= 0 ? activeIndex.value : 0
  focusedIndex.value = i
  nextTick(() => {
    cardEls.value[i]?.focus?.()
  })
}

defineExpose({ focusActiveCard })
</script>

<template>
  <div class="theme-grid-wrapper">
    <div v-if="store.presets.length === 0" class="presets-error">
      Couldn't load themes.
    </div>
    <div role="radiogroup" aria-label="Reader theme" class="theme-grid">
      <ThemeCard
        v-for="(c, idx) in cards"
        :key="c.key"
        :ref="(el) => setCardRef(idx, el)"
        :label="c.label"
        :bg="c.bg"
        :fg="c.fg"
        :active="isActive(c)"
        :tabindex="idx === focusedIndex ? 0 : -1"
        :empty-custom="c.type === 'custom' && c.empty === true"
        @click="onCardClick(idx)"
        @keydown="(e: KeyboardEvent) => onCardKeydown(e, idx)"
      />
      <div
        v-for="i in emptyCellCount"
        :key="`empty-${i}`"
        class="empty-cell"
        aria-hidden="true"
        style="pointer-events: none"
      />
    </div>
  </div>
</template>

<style scoped>
.theme-grid-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.theme-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}
.empty-cell {
  border: none;
  background: transparent;
}
.presets-error {
  font-size: 0.8125rem;
  color: var(--color-text-secondary, #666);
  padding: 0.5rem 0.25rem;
}
</style>
