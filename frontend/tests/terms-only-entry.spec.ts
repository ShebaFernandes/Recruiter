import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_TERMS_ONLY !== '1', 'Requires isolated terms-only local setup')
for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`signup without legal notices or age/country/checkboxes at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled()
    await expect(page.getByText(/By continuing|Read our Privacy Policy/)).toHaveCount(0)
    await page.screenshot({ path: `/private/tmp/enter-terms-only-google-entry-${viewport.width}.png`, animations: 'disabled', fullPage: true })
    await page.getByText('Continue with email', { exact: true }).click()
    await expect(page.getByLabel('Full name')).toBeVisible()
    await expect(page.getByRole('checkbox')).toHaveCount(0)
    await expect(page.getByText(/Required confirmations|at least 18|These are your declarations/)).toHaveCount(0)
    await expect(page.locator('input[name="country_code"], input[name="age_version"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeEnabled()
    await page.screenshot({ path: `/private/tmp/enter-terms-only-signup-${viewport.width}.png`, animations: 'disabled', fullPage: true })
  })
}
