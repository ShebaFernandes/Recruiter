import { expect, test } from '@playwright/test'

for (const width of [1440, 1024, 390]) {
  test(`recruiter entry requires login and has no guest or signup controls at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const guestRequests: string[] = []
    page.on('request', request => {
      if (request.url().includes('/guest/')) guestRequests.push(request.url())
    })
    await page.goto('/')
    await page.getByTestId('for-recruiters').click()
    await expect(page).toHaveURL(/\/recruiter$/)
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await expect(page.getByLabel('Candidate search')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Create.*account/i })).toHaveCount(0)
    await page.getByLabel('Email').focus()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Password', { exact: true })).toBeFocused()
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    expect(guestRequests).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath(`recruiter-login-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: '← Back to Enter' }).click()
    await page.getByTestId('for-candidates').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  })
}
