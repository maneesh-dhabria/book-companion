/**
 * Quiz e2e seed helpers (T35).
 *
 * Seeds rows directly via the same-origin Vite/serve backend through a
 * lightweight set of fetches. Heavier LLM-driven setup (seeding warm-up
 * concepts, populating Book.pre_drafted_q1_id) requires either a
 * BOOKCOMPANION_TEST_MODE=1 admin route or a sqlite3 shell — both deferred
 * to a follow-up. Each spec that needs that flavor uses `test.fixme(...)`
 * with the seeding TODO inline.
 */

import type { APIRequestContext } from '@playwright/test'

export async function getFirstBookId(request: APIRequestContext): Promise<number | null> {
  const r = await request.get('/api/v1/books')
  if (!r.ok()) return null
  const body = await r.json()
  const books = (body.books ?? body) as Array<{ id: number }>
  return books.length > 0 ? books[0].id : null
}

export async function quizPathForBook(bookId: number): Promise<string> {
  return `/books/${bookId}?tab=quiz`
}
