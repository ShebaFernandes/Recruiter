import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  workers: 1,
  testMatch: process.env.E2E_LEGAL_PHASE === 'published'
    ? ['**/legal-review.spec.ts', '**/legal-published.spec.ts', '**/candidate-navigation.spec.ts']
    : process.env.E2E_LEGAL_PHASE === 'worker'
    ? ['**/recruiter-flow.spec.ts', '**/permanent-preferences.spec.ts', '**/candidate-recruiter-connection.spec.ts']
    : '**/*.spec.ts',
  testIgnore: ['published', 'worker'].includes(process.env.E2E_LEGAL_PHASE || '') ? [] : [
    '**/legal-review.spec.ts', '**/legal-published.spec.ts', '**/candidate-navigation.spec.ts',
    '**/recruiter-flow.spec.ts', '**/permanent-preferences.spec.ts', '**/candidate-recruiter-connection.spec.ts',
  ],
  timeout: 30_000,
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || 'test-results',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
})
