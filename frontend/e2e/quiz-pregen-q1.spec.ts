/**
 * Pre-gen instant Q1 journey (spec §14.3, NFR-01):
 * seed `Book.pre_drafted_q1_id` → click Start → assert Q1 visible <500ms
 * (no spinner).
 */

import { test, expect } from '@playwright/test'

test.describe('quiz pre-gen Q1 journey', () => {
  test.fixme(
    'pre-gen slot bypasses the loading spinner (NFR-01: <500ms)',
    async ({ page }) => {
      // TODO: seed `books.pre_drafted_q1_id` via sqlite shell (or a
      //       BOOKCOMPANION_TEST_MODE admin route). Then click Start and time
      //       the click → first-question-stem render — must be <500ms.
      await page.goto('/books/1?tab=quiz')
      const t0 = Date.now()
      await page.getByRole('button', { name: /start quiz/i }).click()
      await expect(page.getByTestId('question-stem')).toBeVisible()
      const elapsed = Date.now() - t0
      expect(elapsed).toBeLessThan(500)
      // Spinner copy must NOT appear in the pre-gen path.
      await expect(
        page.getByText(/Reading the book to draft your question/i),
      ).toHaveCount(0)
    },
  )
})
