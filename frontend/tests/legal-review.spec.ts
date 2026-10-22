import { expect, test } from '@playwright/test'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(purpose => [purpose, {
  text: purpose === 'age' ? 'I confirm that I am at least 18 years old.' : `UNPUBLISHED ${purpose} synthetic review content`,
  version: `unpublished-${purpose}-fixture`, sha256: 'fixture', unpublished: true,
}]))

test('unavailable documents block signup until explicit retry succeeds', async ({ page }) => {
  await page.route('**/*.mp4', route => route.abort())
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
  let available = false
  await page.route('**/api/v1/legal/documents/', route => route.fulfill(available
    ? { json: { enabled: true, documents } } : { status: 503, json: {} }))
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeDisabled()
  await expect(page.getByRole('alert')).toContainText('could not load')
  available = true
  await page.getByRole('button', { name: 'Retry / review current legal documents' }).click()
  await expect(page.getByRole('checkbox')).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeEnabled()
})

for (const width of [390, 768, 1440]) {
  test(`unpublished review and independent confirmations at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.route('**/*.mp4', route => route.abort())
    await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
    await page.route('**/api/v1/legal/documents/', route => route.fulfill({ json: { enabled: true, documents } }))
    await page.route('**/api/v1/auth/csrf/', route => route.fulfill({ json: { csrfToken: 'synthetic' } }))
    let posted = false
    await page.route('**/api/v1/auth/signup/', async route => {
      posted = true
      const body = route.request().postDataJSON()
      expect(body.age_accepted).toBe(true)
      expect(body.terms_accepted).toBe(true)
      expect(body.terms_version).toBe(documents.terms.version)
      await route.fulfill({ status: 201, json: { requires_email_verification: true, detail: 'Synthetic verification only.' } })
    })
    await page.goto('/')
    await page.getByTestId('for-candidates').click()
    await page.getByLabel('Full name').fill('Synthetic Candidate')
    await page.getByLabel('Email', { exact: true }).fill('synthetic@example.test')
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-password-123!')
    const checks = page.getByRole('checkbox')
    await expect(checks).toHaveCount(2)
    await expect(checks.nth(0)).not.toBeChecked()
    await expect(checks.nth(1)).not.toBeChecked()
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    expect(posted).toBe(false)
    await checks.nth(0).check()
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    expect(posted).toBe(false)
    await page.screenshot({ path: info.outputPath(`legal-review-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await checks.nth(1).check()
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    await expect(page.getByText('Synthetic verification only.')).toBeVisible()
    for (const kind of ['privacy', 'terms']) {
      await page.goto(`/${kind}`)
      await expect(page.getByText(`UNPUBLISHED ${kind} synthetic review content`)).toBeVisible()
    }
  })
}
