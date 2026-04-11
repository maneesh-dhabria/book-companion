<script setup lang="ts">
import { useAIThreadsStore } from '@/stores/aiThreads'
import { onMounted } from 'vue'

const props = defineProps<{
  bookId: number
}>()

const emit = defineEmits<{
  select: [threadId: number]
  new: []
}>()

const store = useAIThreadsStore()

onMounted(() => store.loadThreads(props.bookId))
</script>

<template>
  <div class="thread-list">
    <button class="new-thread-btn" @click="$emit('new')">+ New Thread</button>
    <div v-if="store.loading" class="loading">Loading...</div>
    <div v-else-if="store.threads.length === 0" class="empty">
      No conversations yet. Start a new thread to chat about this book.
    </div>
    <button
      v-for="thread in store.threads"
      :key="thread.id"
      class="thread-item"
      @click="$emit('select', thread.id)"
    >
      <span class="thread-title">{{ thread.title }}</span>
      <span class="thread-meta">
        {{ thread.message_count }} messages
        &middot;
        {{ new Date(thread.updated_at).toLocaleDateString() }}
      </span>
      <span v-if="thread.last_message_preview" class="thread-preview">
        {{ thread.last_message_preview }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.thread-list { padding: 0.75rem; display: flex; flex-direction: column; gap: 0.375rem; }
.new-thread-btn { padding: 0.5rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; font-size: 0.85rem; margin-bottom: 0.5rem; }
.loading, .empty { text-align: center; padding: 1.5rem; color: var(--color-text-secondary, #888); font-size: 0.85rem; }
.thread-item { display: flex; flex-direction: column; gap: 0.125rem; padding: 0.625rem; border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.375rem; background: var(--color-bg, #fff); cursor: pointer; text-align: left; }
.thread-item:hover { background: var(--color-bg-hover, #f9fafb); }
.thread-title { font-size: 0.85rem; font-weight: 500; }
.thread-meta { font-size: 0.7rem; color: var(--color-text-secondary, #888); }
.thread-preview { font-size: 0.75rem; color: var(--color-text-secondary, #666); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
