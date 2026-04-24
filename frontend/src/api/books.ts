import type { Book, BookListItem, PaginatedResponse } from '@/types'
import { apiClient } from './client'

export interface ListBooksParams {
  page?: number
  per_page?: number
  status?: string
  format?: string
  q?: string
  tag?: string
  sort_field?: string
  sort_direction?: string
}

export function listBooks(
  params?: ListBooksParams,
  options?: { signal?: AbortSignal },
) {
  return apiClient.get<PaginatedResponse<BookListItem>>(
    '/books',
    params as Record<string, string | number | boolean | undefined>,
    options,
  )
}

export function getBook(id: number) {
  return apiClient.get<Book>(`/books/${id}`)
}

export function uploadBook(file: File) {
  return apiClient.upload<Book>('/books/upload', file)
}

export function updateBook(id: number, data: { title?: string }) {
  return apiClient.patch<Book>(`/books/${id}`, data)
}

export function deleteBook(id: number) {
  return apiClient.delete(`/books/${id}`)
}

export function checkDuplicate(fileHash: string) {
  return apiClient.post<{ is_duplicate: boolean; existing_book_id: number | null }>(
    '/books/check-duplicate',
    { file_hash: fileHash },
  )
}
