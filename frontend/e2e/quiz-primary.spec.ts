/**
 * Quiz primary journey (spec §14.3).
 *
 * Walking-skeleton: empty state → All Summaries → Start → answer → self-assess
 * → next → stop → Past panel renders.
 *
 * Static structure assertions run unconditionally; LLM-driven assertions are
 * marked `test.fixme` until backend test-seed infrastructure lands.
 */

import { test, expect } from '@playwright/test'
import { getFirstBookId } from './fixtures/quiz_seed'

test.describe('quiz primary journey', () => {
  test('renders the Quiz tab shell with scope picker for a seeded book', async ({
    page,
    request,
  }) => {
    const bookId = await getFirstBookId(request)
    test.skip(bookId === null, 'No seeded books — run `bookcompanion add` first.')
    await page.goto(`/books/${bookId}?tab=quiz`)
    await expect(page.getByTestId('quiz-tab-root')).toBeVisible()
    // Either the no-llm/no-summaries banner OR scope-picker should be visible.
    const root = page.getByTestId('quiz-tab-root')
    const mode = await root.getAttribute('data-mode')
    expect(['no-llm', 'no-summaries', 'ready', 'resume', 'active']).toContain(mode!)
  })

  test.fixme(
    'full primary journey: Start → answer → self-assess → next → stop',
    async ({ page }) => {
      // Requires:
      //  - A book with at least one summary
      //  - Working LLM provider
      //  - ≥30s timeout per LLM call
      // TODO: seed via /api/v1/books/{id}/summarize and a BOOKCOMPANION_TEST_MODE
      //       fast-path that returns a deterministic question.
      await page.goto('/books/1?tab=quiz')
      await page.getByRole('radio', { name: /all summaries/i }).check()
      await page.getByRole('button', { name: /start quiz/i }).click()
      await expect(
        page
          .getByText(/Reading the book to draft your question/i)
          .or(page.getByTestId('question-stem')),
      ).toBeVisible({ timeout: 30_000 })
      await page.getByTestId('open-input').fill('My answer.')
      await page.getByRole('button', { name: /submit/i }).click()
      await expect(page.getByTestId('feedback-correct')).toBeVisible({ timeout: 30_000 })
      await page.getByRole('button', { name: /got it/i }).click()
      await page.getByRole('button', { name: /stop session/i }).click()
      await expect(page.getByText(/past q/i)).toBeVisible()
    },
  )
})
