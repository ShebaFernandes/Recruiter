import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_AUTH_NAVIGATION !== '1', 'Requires isolated local browser-test servers')

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`Apply stays at the top of the job description at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/opportunities?role=backend-engineer')
    const dialog = page.getByRole('dialog', { name: 'Job description' })
    const apply = dialog.getByRole('button', { name: 'Apply now', exact: true })
    await expect(apply).toBeInViewport()
    await expect(dialog.getByRole('button', { name: 'Close job description' })).toBeInViewport()
    await expect(dialog.getByRole('region', { name: 'Full job description' })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(apply).toBeFocused()
    const button = await apply.boundingBox()
    expect(button!.y).toBeLessThan(150)
    await page.screenshot({ path: `/private/tmp/enter-opportunity-top-apply-${viewport.width}.png`, fullPage: false, animations: 'disabled' })
    if (viewport.width < 761) {
      await dialog.evaluate(el => { el.scrollTop = el.scrollHeight })
    } else {
      await dialog.getByRole('region', { name: 'Full job description' }).evaluate(el => { el.scrollTop = el.scrollHeight })
    }
    await expect(apply).toBeInViewport()
    let submissions = 0
    page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/opportunities/applications/')) submissions++ })
    await apply.click()
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible()
    expect(new URL(page.url()).searchParams.get('role')).toBe('backend-engineer')
    expect(new URL(page.url()).searchParams.get('apply')).toBe('1')
    expect(submissions).toBe(0)
  })
}
