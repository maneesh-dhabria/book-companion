import {
  createThread,
  deleteThread,
  getThread,
  listThreads,
  sendMessage,
  updateThread,
} from '@/api/aiThreads'
import type { AIMessage, AIThread, AIThreadListItem } from '@/types'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAIThreadsStore = defineStore('aiThreads', () => {
  const threads = ref<AIThreadListItem[]>([])
  const currentThread = ref<AIThread | null>(null)
  const loading = ref(false)
  const sending = ref(false)

  async function loadThreads(bookId: number) {
    loading.value = true
    try {
      threads.value = await listThreads(bookId)
    } finally {
      loading.value = false
    }
  }

  async function openThread(threadId: number) {
    loading.value = true
    try {
      currentThread.value = await getThread(threadId)
    } finally {
      loading.value = false
    }
  }

  async function startNewThread(bookId: number, title?: string) {
    const thread = await createThread(bookId, title)
    currentThread.value = thread
    // Refresh list
    await loadThreads(bookId)
    return thread
  }

  async function renameThread(threadId: number, title: string) {
    await updateThread(threadId, title)
    if (currentThread.value?.id === threadId) {
      currentThread.value.title = title
    }
    const listItem = threads.value.find((t) => t.id === threadId)
    if (listItem) listItem.title = title
  }

  async function removeThread(threadId: number, bookId: number) {
    await deleteThread(threadId)
    if (currentThread.value?.id === threadId) {
      currentThread.value = null
    }
    threads.value = threads.value.filter((t) => t.id !== threadId)
  }

  async function send(
    content: string,
    contextSectionId?: number | null,
    selectedText?: string | null,
  ): Promise<AIMessage | null> {
    if (!currentThread.value) return null
    sending.value = true
    try {
      // Optimistically add user message
      const userMsg: AIMessage = {
        id: -Date.now(),
        thread_id: currentThread.value.id,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      }
      currentThread.value.messages.push(userMsg)

      const response = await sendMessage(
        currentThread.value.id,
        content,
        contextSectionId,
        selectedText,
      )

      // Replace optimistic user message with real one and add assistant response
      // The server stores both — re-fetch for accurate state
      currentThread.value = await getThread(currentThread.value.id)
      return response
    } finally {
      sending.value = false
    }
  }

  return {
    threads,
    currentThread,
    loading,
    sending,
    loadThreads,
    openThread,
    startNewThread,
    renameThread,
    removeThread,
    send,
  }
})
