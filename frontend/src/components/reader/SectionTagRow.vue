<template>
  <div class="section-tag-row" v-if="sectionId">
    <TagChip
      v-for="t in tags"
      :key="t.id"
      :label="t.name"
      :color="t.color"
      removable
      @remove="removeTag(t.id)"
    />
    <TagChipInput
      :model-value="[]"
      :suggest="suggest"
      placeholder="+ section tag…"
      @update:model-value="addTags"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import TagChip from '@/components/common/TagChip.vue'
import TagChipInput from '@/components/common/TagChipInput.vue'

interface TagEntry {
  id: number
  name: string
  color: string | null
}

const props = defineProps<{ sectionId: number | null }>()

const tags = ref<TagEntry[]>([])

async function load() {
  if (!props.sectionId) return
  const r = await fetch(`/api/v1/sections/${props.sectionId}/tags`)
  if (r.ok) tags.value = (await r.json()).tags
}

async function suggest(q: string) {
  const r = await fetch(`/api/v1/tags/suggest?q=${encodeURIComponent(q)}`)
  if (!r.ok) return []
  const body = await r.json()
  return (body.suggestions || []).map((s: { name: string }) => s.name)
}

async function addTags(names: string[]) {
  if (!props.sectionId) return
  for (const name of names) {
    const r = await fetch(`/api/v1/sections/${props.sectionId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (r.ok) {
      const body = await r.json()
      if (!tags.value.some((t) => t.id === body.id)) tags.value.push(body)
    }
  }
}

async function removeTag(id: number) {
  if (!props.sectionId) return
  await fetch(`/api/v1/sections/${props.sectionId}/tags/${id}`, { method: 'DELETE' })
  tags.value = tags.value.filter((t) => t.id !== id)
}

watchEffect(() => {
  // Re-fetch when the section id changes so the reader's next/prev
  // navigation keeps the chip row in sync.
  load()
})
</script>

<style scoped>
.section-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  padding: 0.35rem 0;
  min-height: 1.75rem;
}
</style>
