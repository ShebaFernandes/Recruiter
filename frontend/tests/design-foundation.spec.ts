import { expect, test } from '@playwright/test'

test.describe('landing and authentication foundation', () => {
  test('landing and candidate auth stay usable on desktop', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 960 })
    await page.goto('/')

    await expect(page.getByRole('heading', { name: /The best teams are built by ENTER/ })).toBeVisible()
    await expect(page.getByTestId('for-recruiters')).toBeVisible()
    await expect(page.getByTestId('for-candidates')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440)
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: testInfo.outputPath('landing-desktop.png'), fullPage: true, animations: 'disabled' })

    await page.getByTestId('for-candidates').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expect(page.getByLabel('Full name')).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()

    await page.getByRole('button', { name: /Already have an account/ }).click()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await page.getByRole('button', { name: 'Forgot password?' }).click()
    await expect(page.getByRole('heading', { name: 'Forgot your password?' })).toBeVisible()

    await page.goto('/')
    await page.getByTestId('for-recruiters').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expect(page.getByLabel('Company')).toBeVisible()
  })

  test('landing and candidate auth do not overflow on mobile', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /The best teams are built by ENTER/ })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: testInfo.outputPath('landing-mobile.png'), fullPage: true, animations: 'disabled' })

    await page.getByTestId('for-candidates').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  })

  test('landing and recruiter auth adapt at tablet width', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1024, height: 900 })
    await page.goto('/')
    await expect(page.getByTestId('for-recruiters')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1024)
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: testInfo.outputPath('landing-tablet.png'), fullPage: true, animations: 'disabled' })

    await page.getByTestId('for-recruiters').click()
    await expect(page.getByLabel('Company')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1024)
  })

  test('audience navigation opens existing flows directly without anchor scrolling', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#career-story')).toHaveCount(0)
    await expect(page.locator('.ce-intro').getByRole('button')).toHaveCount(0)
    const nav = page.getByRole('navigation', { name: 'Main navigation' })
    await expect(nav.locator('.ce-audience-link svg')).toHaveCount(0)
    await expect(page.locator('.ce-headline-wordmark image')).toHaveAttribute('href', '/enter-wordmark.svg')
    await nav.getByRole('button', { name: 'For recruiters' }).click()
    // No guest backend is enabled by a visual-only landing change.
    await expect(page.getByLabel('Company')).toBeVisible()
    expect(new URL(page.url()).hash).toBe('')
    await page.getByRole('button', { name: '← Back to Enter' }).click()
    await nav.getByRole('button', { name: 'For candidates' }).click()
    expect(new URL(page.url()).hash).toBe('')
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  })

  test('navigation login opens the existing role-specific login forms', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    const login = page.locator('.ce-login summary')
    await login.click()
    await expect(page.getByRole('button', { name: 'Recruiter log in' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
    await login.press('Escape')
    await expect(page.getByRole('button', { name: 'Recruiter log in' })).not.toBeVisible()
    await expect(login).toBeFocused()
    for (const role of ['Recruiter', 'Candidate']) {
      await login.press('Enter')
      await page.getByRole('button', { name: `${role} log in` }).click()
      await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
      await expect(page.getByLabel('Email')).toBeVisible()
      await expect(page.getByLabel('Password', { exact: true })).toBeVisible()
      await expect(page.getByLabel('Full name')).toHaveCount(0)
      await expect(page.getByText(role === 'Recruiter' ? 'RECRUITER WORKSPACE' : 'CANDIDATE PROFILE', { exact: true })).toBeVisible()
      await page.getByRole('button', { name: '← Back to Enter' }).click()
      await login.focus()
    }
    await page.getByTestId('for-candidates').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  })
})
