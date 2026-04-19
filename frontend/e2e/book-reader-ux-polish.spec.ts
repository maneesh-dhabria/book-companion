import { expect, test } from '@playwright/test'

const BASE = process.env.BC_BASE_URL ?? 'http://localhost:8765'
const BOOK_ID = Number(process.env.BC_BOOK_ID ?? 1)

test.use({ baseURL: BASE })

test('book reader UX polish — end-to-end walkthrough', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // --- Scenario 1: landing-section precedence ---
  await page.goto(`/books/${BOOK_ID}`)
  await page.waitForLoadState('networkidle')

  // Progress counter shows only summarizable sections
  const progressText = await page.getByText(/\d+ of \d+ sections summarized/).first().textContent()
  expect(progressText).toMatch(/0 of 22 sections summarized/)

  // Landing lands on the first summarizable section. Table of Contents (front-matter)
  // must NOT be the landing section.
  const currentTitle = await page.locator('.toc-trigger').textContent()
  expect(currentTitle?.toLowerCase()).not.toContain('contents')

  // --- Scenario 2: TOC Front Matter accordion ---
  await page.locator('.toc-trigger').click()
  const details = page.locator('.toc-dropdown details')
  await expect(details).toBeVisible()
  const summaryText = await details.locator('summary').textContent()
  expect(summaryText).toMatch(/Front Matter \(\d+\)/)
  // Default-collapsed
  expect(await details.evaluate((el: HTMLDetailsElement) => el.open)).toBe(false)

  // Body section (chapter) renders outside the accordion
  const bodyTitles = await page
    .locator('.toc-list > .toc-item .toc-title')
    .allInnerTexts()
  expect(bodyTitles.some((t) => /Chapter I\. LAYING PLANS/i.test(t))).toBe(true)
  // "Contents" (table_of_contents) must be inside the accordion, not body
  expect(bodyTitles.some((t) => /^Contents$/.test(t))).toBe(false)

  // Expand the accordion to verify Contents is there
  await details.locator('summary').click()
  const accordionTitles = await details
    .locator('.toc-item .toc-title')
    .allInnerTexts()
  expect(accordionTitles).toContain('Contents')

  // --- Scenario 3: Summary tab on a front-matter section ---
  // Navigate to "Contents" (front-matter) and toggle to Summary
  const contentsLink = details.locator('.toc-item', { hasText: 'Contents' }).first()
  await contentsLink.click()
  await page.waitForLoadState('networkidle')
  // Toggle to Summary view (hidden on front-matter in some flows — we click the
  // reader-header toggle regardless and assert the empty-state text).
  const summaryToggle = page.getByRole('button', { name: /Summary/i }).first()
  if (await summaryToggle.isVisible().catch(() => false)) {
    await summaryToggle.click()
  }
  // SummaryEmptyState renders the "not applicable" copy with the section title
  await expect(page.getByText(/Summary not applicable for Contents/i)).toBeVisible()

  // --- Scenario 4: Summary tab on a chapter without summary ---
  await page.locator('.toc-trigger').click()
  const chapterLink = page
    .locator('.toc-list > .toc-item')
    .filter({ hasText: 'Chapter I. LAYING PLANS' })
    .first()
  await chapterLink.click()
  await page.waitForLoadState('networkidle')
  const toggleChapter = page.getByRole('button', { name: /Summary/i }).first()
  if (await toggleChapter.isVisible().catch(() => false)) {
    await toggleChapter.click()
  }
  await expect(page.getByText(/Not yet summarized/i)).toBeVisible()
  await expect(
    page.getByRole('button', { name: /Summarize this section/i }),
  ).toBeVisible()

  // --- Scenario 5: Summarize pending button disabled logic + visibility ---
  // Button is visible in the header and enabled (no active job yet).
  const pendingBtn = page.getByRole('button', { name: /Summarize pending sections/i })
  await expect(pendingBtn).toBeVisible()
  await expect(pendingBtn).toBeEnabled()

  // --- Scenario 6: link policy — external anchors get target=_blank, relative become spans ---
  // Switch back to Original content on a chapter to inspect the rendered markup.
  const toggleOriginal = page.getByRole('button', { name: /(Original|Content)/i }).first()
  if (await toggleOriginal.isVisible().catch(() => false)) {
    await toggleOriginal.click()
  }
  // Anchor elements: any <a> present must have target=_blank + rel=noopener noreferrer
  const anchorCount = await page.locator('.reading-area a').count()
  if (anchorCount > 0) {
    const externalAnchorsOk = await page.locator('.reading-area a').evaluateAll(
      (els) =>
        (els as HTMLAnchorElement[]).every(
          (a) =>
            a.target === '_blank' &&
            (a.rel || '').includes('noopener') &&
            (a.rel || '').includes('noreferrer'),
        ),
    )
    expect(externalAnchorsOk).toBe(true)
  }
  // No <a href="#..."> or <a href="./..."> or <a href="javascript:..."> survived
  const relativeAnchors = await page
    .locator(
      '.reading-area a[href^="#"], .reading-area a[href^="./"], .reading-area a[href^="../"], .reading-area a[href^="javascript:"]',
    )
    .count()
  expect(relativeAnchors).toBe(0)

  // --- Screenshot evidence ---
  await page.screenshot({
    path: 'e2e/artifacts/ux-polish-final.png',
    fullPage: true,
  })

  // Console must be free of unexpected errors
  const unexpectedErrors = consoleErrors.filter(
    (e) => !e.includes('favicon') && !e.includes('Failed to load resource'),
  )
  expect(unexpectedErrors, unexpectedErrors.join('\n')).toEqual([])
})
