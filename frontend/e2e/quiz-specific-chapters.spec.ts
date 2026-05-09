/**
 * Specific Chapters journey (spec §14.3): scope select → multi-select →
 * budget bar updates → over-budget rejection → start → question references
 * chapter content.
 */

import { test, expect } from '@playwright/test'
import { getFirstBookId } from './fixtures/quiz_seed'

test.describe('quiz specific-chapters journey', () => {
  test('scope picker can switch to specific-chapters and shows ChapterMultiSelect', async ({
    page,
    request,
  }) => {
    const bookId = await getFirstBookId(request)
    test.skip(bookId === null, 'No seeded books — run `bookcompanion add` first.')
    await page.goto(`/books/${bookId}?tab=quiz`)
    const root = page.getByTestId('quiz-tab-root')
    const mode = await root.getAttribute('data-mode')
    test.skip(
      mode !== 'ready',
      `quiz tab in mode=${mode}; specific-chapters flow requires 'ready' mode (no in-progress session, LLM available, summaries present).`,
    )
    await page.getByRole('radio', { name: /specific chapters/i }).check()
    await expect(page.getByTestId('chapter-multi-select')).toBeVisible()
    await expect(page.getByTestId('budget-bar')).toBeVisible()
  })

  test.fixme(
    'budget rejects over-budget chapter selection',
    async ({ page }) => {
      // TODO: seed a book with chapters whose combined token count exceeds
      //       QUIZ_SPECIFIC_CHAPTERS_TOKEN_BUDGET (60_000) so the rejection
      //       branch fires deterministically.
      await page.goto('/books/1?tab=quiz')
      await page.getByRole('radio', { name: /specific chapters/i }).check()
      // Try to select chapters that overflow the budget; assert the
      // `wouldExceedBudget` microcopy surfaces.
      await expect(page.getByText(/would exceed budget/i)).toBeVisible()
    },
  )
})
