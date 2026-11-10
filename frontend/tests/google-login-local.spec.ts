import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_GOOGLE_LOCAL !== '1', 'Requires isolated local servers and synthetic email links')

// Run only against an isolated local backend with OAuth disabled and local email links enabled.
test('candidate signup, verification, logout and password login remain available', async ({ page }) => {
  test.setTimeout(60_000)
  const email = `oauth-fallback-${Date.now()}@example.test`
  const password = 'Synthetic-browser-password-123!'
  await page.goto('/')
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeDisabled()
  await page.screenshot({ path: '/private/tmp/enter-google-login-signup.png', fullPage: true })
  await page.getByText('Continue with email', { exact: true }).click()
  await page.getByLabel('Full name').fill('Synthetic OAuth Fallback')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 15_000 })
  const verify = page.getByRole('link', { name: 'Verify this local account' })
  await expect(verify).toBeVisible()
  await verify.click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).not.toBeVisible()
  await expect.poll(async () => {
    const response = await page.request.get('http://127.0.0.1:18010/api/v1/auth/me/')
    return response.status()
  }).toBe(200)
  // Reload to leave the consumed verification URL and exercise cookie-based identity restore.
  await page.goto('/')
  await expect(page.getByRole('button', { name: /Synthetic OAuth Fallback/ })).toBeVisible()
  await page.getByRole('button', { name: /Synthetic OAuth Fallback/ }).click()
  await page.getByRole('button', { name: 'Log Out', exact: true }).click()
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeDisabled()
  await page.screenshot({ path: '/private/tmp/enter-google-login-login.png', fullPage: true })
  await page.getByText('Continue with email', { exact: true }).click()
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page.getByRole('button', { name: /Synthetic OAuth Fallback/ })).toBeVisible()
})

test('candidate Google option is visible on mobile and absent from recruiter login', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: '/private/tmp/enter-google-login-mobile.png', fullPage: true })
  await page.goto('/recruiter')
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toHaveCount(0)
})

test('cancelled Google sign-in provides a safe return path', async ({ page }) => {
  await page.goto('/auth/google?result=cancelled')
  await expect(page.getByText(/Google sign-in was cancelled/)).toBeVisible()
  await expect(page.getByRole('link', { name: 'Return to ENTER' })).toHaveAttribute('href', '/')
})


test('enabled Google UI keeps Google as the primary candidate action', async ({ page }) => {
  // Visual-only configuration stub: does not contact Google or enable the backend.
  await page.route('**/auth/google/config/', route => route.fulfill({ json: { enabled: true } }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveClass(/ui-button--secondary/)
  await page.screenshot({ path: '/private/tmp/enter-google-login-enabled.png', fullPage: true })
})
