import { expect, test } from '@playwright/test'
import { issueLocalAccountToken } from './account-token'

const documents = Object.fromEntries(['age', 'terms', 'privacy', 'submission'].map(purpose => [purpose, {
  text: `${purpose} synthetic published text`, version: `enter-candidate-${purpose}-v1.0`,
  sha256: `synthetic-${purpose}`, unpublished: false,
}]))

for (const width of [390, 1440]) {
  for (const staleSession of [false, true]) {
    test(`candidate entry stays open at ${width}px with ${staleSession ? 'expired' : 'no'} session`, async ({ page, context, baseURL }) => {
      await page.setViewportSize({ width, height: 900 })
      if (staleSession) await context.addCookies([{ name: 'enter_session', value: 'invalid-synthetic-session', url: baseURL! }])
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
      await page.route('**/api/v1/legal/documents/', async route => {
        const cookie = await route.request().headerValue('cookie')
        // Reproduce production: even this public endpoint rejects an invalid cookie.
        await route.fulfill(cookie?.includes('enter_session=')
          ? { status: 401, json: { detail: 'Invalid token.' } }
          : { json: { enabled: true, documents } })
      })
      await page.goto('/')
      await page.getByTestId('for-candidates').click()
      await expect(page.getByRole('group', { name: 'Required confirmations' })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
      await page.getByLabel('Full name').fill('Synthetic Candidate')
      await expect(page.getByLabel('Full name')).toHaveValue('Synthetic Candidate')
      await page.getByRole('button', { name: /Back to ENTER/i }).click()
      await page.getByText('Log in', { exact: true }).click()
      const loginDocuments = page.waitForResponse(response => response.url().endsWith('/legal/documents/') && response.status() === 200)
      await page.getByRole('button', { name: 'Candidate log in' }).click()
      await loginDocuments
      await expect(page.getByRole('button', { name: 'Retry / review current legal documents' })).toHaveCount(0)
      await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
      expect(errors).toEqual([])
      await expect(page.getByTestId('for-recruiters')).toHaveCount(0)
    })
  }
}

test('failed public legal request stays on signup and blocks acceptance', async ({ page }) => {
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
  await page.route('**/api/v1/legal/documents/', route => route.fulfill({ status: 401, json: {} }))
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('alert')).toContainText('Acceptance is blocked')
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeDisabled()
})

test('real isolated signup, verification and returning candidate reach resume upload', async ({ page, context, baseURL }) => {
  test.skip(process.env.RUN_REAL_NAVIGATION_TEST !== 'true', 'Requires the disposable API runner')
  if (!baseURL || new URL(baseURL).hostname !== '127.0.0.1' || !process.env.DATABASE_URL?.includes('/test_enter_e2e_')) throw new Error('Local isolated runner only')
  test.setTimeout(60_000)
  const email = `navigation-${Date.now()}@example.test`
  const password = 'Navigation-isolated-938!'
  await context.addCookies([{ name: 'enter_session', value: 'invalid-synthetic-session', url: baseURL }])
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('group', { name: 'Required confirmations' })).toBeVisible()
  await page.getByLabel('Full name').fill('Navigation Test Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('checkbox').nth(0).check()
  await page.getByRole('checkbox').nth(1).check()
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 15_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  // A valid existing session survives initialization and public document loading.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  await page.getByRole('button', { name: 'Log out' }).click()
  await context.addCookies([{ name: 'enter_session', value: 'invalid-synthetic-session', url: baseURL }])
  await page.goto('/')
  await page.getByText('Log in', { exact: true }).click()
  await page.getByRole('button', { name: 'Candidate log in' }).click()
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Incorrect-password-123!')
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid email or password')
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  await page.getByRole('button', { name: 'Navigation Test Candidate' }).click()
  await page.getByRole('button', { name: 'Delete my account', exact: true }).click()
  await page.getByLabel('Current password', { exact: true }).fill(password)
  await page.getByLabel('Type DELETE to confirm', { exact: true }).fill('DELETE')
  await page.getByRole('button', { name: 'Permanently delete my account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your account has been deleted' })).toBeVisible()
})
