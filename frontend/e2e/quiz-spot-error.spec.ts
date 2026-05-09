/**
 * Spot-the-error journey (spec §14.3): force a spot_error question via
 * stub-provider mode → answer → feedback names the error.
 */

import { test, expect } from '@playwright/test'

test.describe('quiz spot-error journey', () => {
  test.fixme(
    'spot_error shape: callout + correction textarea wires to feedback',
    async ({ page }) => {
      // TODO: requires stub-provider env (BOOKCOMPANION_LLM__PROVIDER=stub or a
      //       test-mode hook that forces `shape='spot_error'` for the next call).
      await page.goto('/books/1?tab=quiz')
      await page.getByRole('button', { name: /start quiz/i }).click()
      await expect(page.getByTestId('intended-error-callout')).toBeVisible({
        timeout: 30_000,
      })
      await page.getByTestId('correction-input').fill('Correct version.')
      await page.getByRole('button', { name: /submit/i }).click()
      await expect(page.getByTestId('feedback-actual')).toContainText(/the wrong/i)
    },
  )
})
