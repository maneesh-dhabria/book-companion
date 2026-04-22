<script setup lang="ts">
import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'
import type { AIMessage } from '@/types'

defineProps<{
  message: AIMessage
}>()
</script>

<template>
  <div class="chat-message" :class="message.role">
    <div class="message-bubble">
      <!-- Assistant replies go through markdown; user messages stay plain text
           so pasted URLs / code fragments aren't reinterpreted. -->
      <MarkdownRenderer
        v-if="message.role === 'assistant'"
        class="message-content"
        :content="message.content"
      />
      <div v-else class="message-content user-text">{{ message.content }}</div>
    </div>
    <div class="message-meta">
      {{ new Date(message.created_at).toLocaleTimeString() }}
    </div>
  </div>
</template>

<style scoped>
.chat-message { display: flex; flex-direction: column; max-width: 85%; }
.chat-message.user { align-self: flex-end; align-items: flex-end; }
.chat-message.assistant { align-self: flex-start; align-items: flex-start; }
.message-bubble { padding: 0.625rem 0.875rem; border-radius: 1rem; font-size: 0.85rem; line-height: 1.4; word-break: break-word; }
.user .message-bubble { background: var(--color-primary, #3b82f6); color: #fff; border-bottom-right-radius: 0.25rem; }
.assistant .message-bubble { background: var(--color-bg-secondary, #f3f4f6); color: var(--color-text, #111); border-bottom-left-radius: 0.25rem; }
.message-meta { font-size: 0.625rem; color: var(--color-text-secondary, #999); margin-top: 0.125rem; padding: 0 0.25rem; }
</style>
