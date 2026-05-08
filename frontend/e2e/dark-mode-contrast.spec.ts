import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

// FR-A06, FR-A07, NFR-01: every chip + body-text pair must meet
// WCAG 2.2 AA contrast (4.5:1 text, 3:1 large text + non-text). The
// sweep runs both themes on the routes most likely to show chips.

const ROUTES = [
  '/',
  '/books/1',
  '/books/1/sections/1',
  '/concepts',
  '/annotations',
] as const

async function setTheme(page: Page, theme: 'light' | 'dark'): Promise<void> {
  await page.evaluate((t) => {
    try {
      localStorage.setItem('theme', t)
    } catch {
      // ignore — the next reload picks it up via the html-class branch.
    }
    document.documentElement.classList.toggle('dark', t === 'dark')
  }, theme)
}

for (const route of ROUTES) {
  for (const theme of ['light', 'dark'] as const) {
    test(`dark-mode contrast — ${route} (${theme})`, async ({ page }) => {
      await page.goto(route)
      await setTheme(page, theme)
      // Reload so app code that branches on `localStorage.theme` at boot
      // (e.g. dark-class injection) takes effect for the entire render.
      await page.reload()
      // Idle wait — body should at least be visible.
      await page.waitForSelector('body', { state: 'visible', timeout: 10_000 })

      const result = await new AxeBuilder({ page })
        .withTags(['wcag2aa'])
        .analyze()

      const contrast = result.violations.filter((v) => v.id === 'color-contrast')
      // Surface the offending nodes if any so the failure is actionable.
      if (contrast.length > 0) {
        const nodes = contrast.flatMap((v) =>
          v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })),
        )
        console.error(`color-contrast violations on ${route} (${theme}):`, nodes)
      }
      expect(contrast).toEqual([])
    })
  }
}
