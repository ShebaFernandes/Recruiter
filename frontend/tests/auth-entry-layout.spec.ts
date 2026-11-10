import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_AUTH_LAYOUT !== '1', 'Read-only layout check against the isolated approved local environment')

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`Google entry is uncluttered and email consent stays enforced at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
    const google = page.getByRole('button', { name: 'Continue with Google', exact: true })
    await expect(google).toBeEnabled()
    await expect(page.getByRole('checkbox')).toHaveCount(0)
    await expect(page.getByLabel('Full name')).toBeHidden()
    await expect(page.getByLabel('Email', { exact: true })).toBeHidden()
    await expect(page.getByText('Continue with email', { exact: true })).toBeVisible()
    await expect(page.locator('.google-login small')).toContainText('These are your declarations; Google sign-in does not verify')
    await expect(google).toBeInViewport()
    await page.screenshot({ path: `/private/tmp/enter-compact-google-entry-${viewport.width}.png`, animations: 'disabled', fullPage: true })
    await page.getByText('Continue with email', { exact: true }).click()
    await expect(page.getByLabel('Email', { exact: true })).toBeVisible()
    const acceptance = page.getByRole('checkbox')
    await expect(acceptance).toBeVisible()
    await expect(acceptance).toHaveAttribute('required', '')
    await expect(acceptance).not.toBeChecked()
    expect(await page.locator('.legal-confirmations').innerText()).not.toContain('enter-candidate-terms-')
    expect(await page.locator('input[name="terms_version"]').inputValue()).toBeTruthy()
    let signups = 0
    page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/auth/signup/')) signups++ })
    await page.getByLabel('Full name').fill('Unsubmitted Synthetic Candidate')
    await page.getByLabel('Email', { exact: true }).fill('unsubmitted-synthetic@example.test')
    await page.getByLabel('Password', { exact: true }).fill('Unsubmitted-synthetic-123!')
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    expect(signups).toBe(0)
    expect(await acceptance.evaluate(el => (el as HTMLInputElement).validity.valueMissing)).toBe(true)
  })
}
