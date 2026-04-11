<script setup lang="ts">
import { listSections } from '@/api/sections'
import type { Section } from '@/types'
import { onMounted, ref } from 'vue'

const props = defineProps<{
  bookId: number
}>()

const emit = defineEmits<{
  complete: []
  back: []
}>()

const sections = ref<Section[]>([])
const loading = ref(true)

onMounted(async () => {
  sections.value = await listSections(props.bookId)
  loading.value = false
})
</script>

<template>
  <div class="structure-review">
    <h2>Review Structure</h2>
    <p class="subtitle">{{ sections.length }} sections detected</p>

    <div v-if="loading" class="loading">Loading sections...</div>
    <div v-else class="section-table">
      <div class="section-row header">
        <span class="col-index">#</span>
        <span class="col-title">Title</span>
        <span class="col-type">Type</span>
      </div>
      <div v-for="section in sections" :key="section.id" class="section-row">
        <span class="col-index">{{ section.order_index + 1 }}</span>
        <span class="col-title">{{ section.title }}</span>
        <span class="col-type type-badge">{{ section.section_type }}</span>
      </div>
    </div>

    <div class="form-actions">
      <button class="secondary-btn" @click="$emit('back')">Back</button>
      <button class="primary-btn" @click="$emit('complete')">Continue</button>
    </div>
  </div>
</template>

<style scoped>
h2 { font-size: 1.25rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--color-text-secondary, #888); margin-bottom: 1rem; }
.loading { text-align: center; padding: 2rem; }
.section-table { border: 1px solid var(--color-border, #ddd); border-radius: 0.5rem; overflow: hidden; margin-bottom: 1.5rem; max-height: 400px; overflow-y: auto; }
.section-row { display: grid; grid-template-columns: 3rem 1fr 6rem; gap: 0.5rem; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--color-border, #f0f0f0); align-items: center; }
.section-row.header { font-weight: 600; font-size: 0.75rem; text-transform: uppercase; color: var(--color-text-secondary, #888); background: var(--color-bg-secondary, #f9fafb); }
.col-index { color: var(--color-text-secondary, #888); font-size: 0.8rem; }
.col-title { font-size: 0.85rem; }
.type-badge { font-size: 0.7rem; text-transform: capitalize; color: var(--color-text-secondary, #666); }
.form-actions { display: flex; justify-content: space-between; }
.primary-btn { padding: 0.5rem 1.25rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; }
.secondary-btn { padding: 0.5rem 1.25rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; }
</style>
