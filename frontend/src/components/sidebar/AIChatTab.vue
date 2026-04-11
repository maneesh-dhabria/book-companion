<script setup lang="ts">
import ChatMessage from './ChatMessage.vue'
import ThreadList from './ThreadList.vue'
import { useAIThreadsStore } from '@/stores/aiThreads'
import { ref } from 'vue'

const props = defineProps<{
  bookId: number
  sectionId?: number
  selectedText?: string
}>()

const store = useAIThreadsStore()
const messageInput = ref('')

async function handleSend() {
  if (!messageInput.value.trim() || store.sending) return
  const content = messageInput.value
  messageInput.value = ''
  await store.send(content, props.sectionId, props.selectedText)
}

async function createAndOpen() {
  await store.startNewThread(props.bookId)
}
</script>

<template>
  <div class="ai-chat-tab">
    <template v-if="!store.currentThread">
      <ThreadList :book-id="bookId" @select="store.openThread($event)" @new="createAndOpen" />
    </template>
    <template v-else>
      <div class="thread-header">
        <button class="back-btn" @click="store.currentThread = null">&larr;</button>
        <span class="thread-title">{{ store.currentThread.title }}</span>
      </div>
      <div class="messages-area">
        <ChatMessage
          v-for="msg in store.currentThread.messages"
          :key="msg.id"
          :message="msg"
        />
        <div v-if="store.sending" class="thinking">Thinking...</div>
      </div>
      <div class="input-area">
        <textarea
          v-model="messageInput"
          placeholder="Ask about this book..."
          @keydown.enter.exact.prevent="handleSend"
          :disabled="store.sending"
          rows="2"
        />
        <button class="send-btn" @click="handleSend" :disabled="store.sending || !messageInput.trim()">
          Send
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-chat-tab { display: flex; flex-direction: column; height: 100%; }
.thread-header { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--color-border, #e0e0e0); }
.back-btn { background: none; border: none; cursor: pointer; font-size: 1rem; color: var(--color-text-secondary, #666); }
.thread-title { font-size: 0.85rem; font-weight: 500; }
.messages-area { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem; }
.thinking { text-align: center; color: var(--color-text-secondary, #888); font-style: italic; padding: 0.5rem; }
.input-area { padding: 0.5rem 0.75rem; border-top: 1px solid var(--color-border, #e0e0e0); display: flex; gap: 0.5rem; align-items: flex-end; }
.input-area textarea { flex: 1; resize: none; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; padding: 0.5rem; font-size: 0.85rem; font-family: inherit; }
.send-btn { padding: 0.5rem 0.75rem; background: var(--color-primary, #3b82f6); color: #fff; border: none; border-radius: 0.375rem; cursor: pointer; font-size: 0.8rem; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
