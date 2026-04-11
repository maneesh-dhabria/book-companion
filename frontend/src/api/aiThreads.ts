import { apiClient } from './client'
import type { AIMessage, AIThread, AIThreadListItem } from '@/types'

export async function listThreads(bookId: number): Promise<AIThreadListItem[]> {
  return apiClient.get<AIThreadListItem[]>(`/books/${bookId}/ai-threads`)
}

export async function createThread(bookId: number, title?: string): Promise<AIThread> {
  return apiClient.post<AIThread>(`/books/${bookId}/ai-threads`, { title: title || 'New Thread' })
}

export async function getThread(threadId: number): Promise<AIThread> {
  return apiClient.get<AIThread>(`/ai-threads/${threadId}`)
}

export async function updateThread(threadId: number, title: string): Promise<AIThread> {
  return apiClient.patch<AIThread>(`/ai-threads/${threadId}`, { title })
}

export async function deleteThread(threadId: number): Promise<void> {
  return apiClient.delete(`/ai-threads/${threadId}`)
}

export async function sendMessage(
  threadId: number,
  content: string,
  contextSectionId?: number | null,
  selectedText?: string | null,
): Promise<AIMessage> {
  return apiClient.post<AIMessage>(`/ai-threads/${threadId}/messages`, {
    content,
    context_section_id: contextSectionId ?? null,
    selected_text: selectedText ?? null,
  })
}

export async function listMessages(threadId: number): Promise<AIMessage[]> {
  return apiClient.get<AIMessage[]>(`/ai-threads/${threadId}/messages`)
}
