import { expect, test } from '@playwright/test'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(purpose => [purpose, {
  text: `${purpose} v1.0 synthetic published fixture`,
  version: `enter-candidate-${purpose}-v1.0`,
  sha256: `synthetic-${purpose}`,
  effective_date: '2026-10-22',
  unpublished: false,
}]))

test('published documents gate registration without granting recruiter sharing', async ({ page }) => {
  await page.route('**/*.mp4', route => route.abort())
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
  await page.route('**/api/v1/legal/documents/', route => route.fulfill({ json: { enabled: true, documents } }))
  await page.route('**/api/v1/auth/csrf/', route => route.fulfill({ json: { csrfToken: 'synthetic' } }))
  let signupBody: Record<string, unknown> | null = null
  await page.route('**/api/v1/auth/signup/', route => {
    signupBody = route.request().postDataJSON()
    return route.fulfill({ status: 201, json: { requires_email_verification: true, detail: 'Synthetic verification only.' } })
  })

  await page.goto('/privacy')
  await expect(page.getByText('Version: enter-candidate-privacy-v1.0 · Effective 2026-10-22')).toBeVisible()
  await expect(page.getByText(/UNPUBLISHED/)).toHaveCount(0)

  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('group', { name: 'Required confirmations' })).toBeVisible()
  await expect(page.getByText(/does not authorize recruiter sharing/)).toBeVisible()
  await page.getByLabel('Full name').fill('Published Synthetic Candidate')
  await page.getByLabel('Email', { exact: true }).fill('published@example.test')
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-password-123!')
  const checks = page.getByRole('checkbox')
  await expect(checks).toHaveCount(2)
  await checks.nth(0).check()
  await checks.nth(1).check()
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByText('Synthetic verification only.')).toBeVisible()
  expect(signupBody).toMatchObject({
    age_accepted: true,
    terms_accepted: true,
    age_version: 'enter-candidate-age-v1.0',
    terms_version: 'enter-candidate-terms-v1.0',
  })
  expect(signupBody).not.toHaveProperty('recruiter_sharing')
})
