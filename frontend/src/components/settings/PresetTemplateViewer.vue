<script setup lang="ts">
import { ref, watch } from 'vue'

interface TemplateFragment {
  dimension: string
  value: string
  path: string
  source: string
}
interface TemplateResponse {
  name: string
  is_system: boolean
  base_template: { path: string; source: string }
  fragments: TemplateFragment[]
}

const props = defineProps<{ name: string }>()

const data = ref<TemplateResponse | null>(null)
const error = ref<string | null>(null)
const loading = ref(false)

async function fetchTemplate(name: string) {
  loading.value = true
  error.value = null
  data.value = null
  try {
    const r = await fetch(`/api/v1/summarize/presets/${encodeURIComponent(name)}/template`)
    if (!r.ok) {
      error.value = r.status === 404 ? 'Template not found.' : `Request failed (${r.status}).`
      return
    }
    data.value = await r.json()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

watch(() => props.name, (n) => fetchTemplate(n), { immediate: true })
</script>

<template>
  <div class="template-viewer">
    <p v-if="loading" class="muted">Loading template…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="data">
      <section>
        <h4>{{ data.base_template.path }}</h4>
        <pre>{{ data.base_template.source }}</pre>
      </section>
      <section v-for="frag in data.fragments" :key="frag.dimension + '/' + frag.value">
        <h4>{{ frag.dimension }}: {{ frag.value }}</h4>
        <pre>{{ frag.source }}</pre>
      </section>
    </template>
  </div>
</template>

<style scoped>
.template-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.template-viewer h4 {
  font-size: 0.85em;
  color: var(--color-text-secondary);
  margin: 0 0 4px;
  font-family: ui-monospace, monospace;
}
.template-viewer pre {
  background: var(--color-bg-muted, #f8fafc);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 0.85em;
  white-space: pre-wrap;
  margin: 0;
  max-height: 240px;
  overflow: auto;
}
.error {
  color: var(--color-text-danger, #b91c1c);
}
.muted {
  color: var(--color-text-secondary);
}
</style>
