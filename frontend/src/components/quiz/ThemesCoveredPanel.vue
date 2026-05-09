<template>
  <section
    v-if="visible"
    data-test="themes-covered"
    class="themes-covered"
  >
    <h3 class="title">Themes covered so far</h3>
    <p class="paragraph">{{ themesSummary }}</p>
    <div v-if="chips.length > 0" class="chips">
      <button
        v-for="(chip, idx) in chips"
        :key="`${chip}-${idx}`"
        type="button"
        data-test="theme-chip"
        class="chip"
        @click="onChip(chip)"
      >
        {{ chip }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ themesSummary: string | null }>()
const emit = defineEmits<{ (e: 'seed-theme', value: string): void }>()

const visible = computed(
  () => props.themesSummary !== null && props.themesSummary.trim().length > 0,
)

// Heuristic chip extraction (FR-94 / D26 / step 2 of plan):
// split the paragraph on commas, semicolons, " and ", or sentence breaks.
// Conservative: keep only chips that look like noun phrases (≤6 words, ≥2 chars).
const chips = computed(() => {
  if (!props.themesSummary) return []
  const text = props.themesSummary.replace(/[.!?]+$/g, '')
  const parts = text
    .split(/,|;|\band\b/i)
    .map((p) => p.trim())
    .filter((p) => p.length >= 2 && p.split(/\s+/).length <= 6)
  // Dedup case-insensitively while preserving order.
  const seen = new Set<string>()
  const out: string[] = []
  for (const p of parts) {
    const k = p.toLowerCase()
    if (!seen.has(k)) {
      seen.add(k)
      out.push(p)
    }
  }
  return out
})

function onChip(value: string) {
  emit('seed-theme', value)
}
</script>

<style scoped>
.themes-covered {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.85rem;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #111827;
}
.paragraph {
  margin: 0;
  font-size: 0.88rem;
  color: #4b5563;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.chip {
  padding: 0.25rem 0.65rem;
  background: white;
  border: 1px solid #c7d2fe;
  color: #4338ca;
  border-radius: 999px;
  font-size: 0.78rem;
  cursor: pointer;
}
.chip:hover {
  background: #eef2ff;
}
</style>
