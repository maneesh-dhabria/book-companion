import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  testDir: here,
  testMatch: /book-reader-ux-polish\.spec\.ts|summarize-live\.spec\.ts/,
  timeout: 600_000,
  retries: 0,
  use: {
    baseURL: process.env.BC_BASE_URL ?? 'http://localhost:8765',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'desktop-chrome', use: { ...devices['Desktop Chrome'] } }],
})
