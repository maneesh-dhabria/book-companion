<script setup lang="ts">
const FONT_FALLBACKS: Record<string, string> = {
  Georgia: "Georgia, 'Lora', 'Merriweather', serif",
  Inter: "'Inter', system-ui, -apple-system, sans-serif",
  Merriweather: "'Merriweather', 'Lora', Georgia, serif",
  'Fira Code': "'Fira Code', 'Source Code Pro', ui-monospace, monospace",
  Lora: "'Lora', 'Merriweather', Georgia, serif",
  'Source Serif Pro': "'Source Serif Pro', 'Lora', 'Merriweather', serif",
}

const props = withDefaults(
  defineProps<{
    label: string
    bg: string
    fg: string
    active: boolean
    tabindex?: number
    emptyCustom?: boolean
    previewFont?: string
    previewSize?: number
  }>(),
  { tabindex: 0, emptyCustom: false, previewFont: '', previewSize: 16 },
)

defineEmits<{ (e: 'click', ev: MouseEvent): void; (e: 'keydown', ev: KeyboardEvent): void }>()

function familyFor(name: string): string {
  return FONT_FALLBACKS[name] ?? name
}

function sampleStyle(): Record<string, string> {
  if (props.emptyCustom || !props.previewFont) return {}
  return {
    fontFamily: familyFor(props.previewFont),
    fontSize: `${props.previewSize}px`,
  }
}
</script>

<template>
  <button
    type="button"
    role="radio"
    :aria-pressed="active"
    :aria-label="`${label} theme`"
    :tabindex="tabindex"
    class="theme-card"
    :class="{ active, 'empty-custom': emptyCustom }"
    :style="
      emptyCustom
        ? { color: '#1f2937' }
        : { background: bg, color: fg }
    "
    @click="(e) => $emit('click', e)"
    @keydown="(e) => $emit('keydown', e)"
  >
    <span class="card-label">{{ label }}</span>
    <span class="card-sample preview-sample" :style="sampleStyle()">{{ emptyCustom ? 'Customise' : 'Aa' }}</span>
    <span v-if="active" class="card-check" aria-hidden="true">✓</span>
  </button>
</template>

<style scoped>
.theme-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  padding: 0.5rem 0.55rem;
  min-height: 64px;
  border: 2px solid transparent;
  border-radius: 0.5rem;
  cursor: pointer;
  text-align: left;
  font-size: 0.8125rem;
  transition: border-color 100ms;
}
.theme-card.empty-custom {
  background: linear-gradient(135deg, #f3f4f6 0%, #d1d5db 100%);
}
.theme-card.active {
  outline: 2px solid var(--color-primary, #4f46e5);
  outline-offset: 2px;
}
.theme-card:focus-visible {
  outline: 2px solid var(--color-primary, #4f46e5);
  outline-offset: 2px;
}
.card-label {
  font-weight: 600;
  font-size: 0.75rem;
}
.card-sample {
  font-size: 1.1rem;
  font-weight: 700;
}
.card-check {
  position: absolute;
  top: 0.25rem;
  right: 0.4rem;
  font-size: 0.85rem;
  color: var(--color-primary, #4f46e5);
  font-weight: 700;
}
</style>
