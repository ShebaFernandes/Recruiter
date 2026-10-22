import { expect, test } from '@playwright/test'

// Exercise the real App now that the authentication stylesheet is available.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
})

for (const width of [1440, 1024, 390]) {
test(`landing motion at ${width}px preserves layout without lower scroll sections`, async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.setViewportSize({ width, height: 960 })
  await page.goto('/')
  await expect(page.locator('.ce-intro h1')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  const layout = () => page.locator('.ce-intro h1').evaluate(element => {
    const node = element as HTMLElement
    return [node.offsetTop, node.offsetLeft, node.offsetWidth, node.offsetHeight]
  })
  const before = await layout()
  // Approved minimal layout keeps the headline static; only the scenery moves.
  await expect(page.locator('.ce-intro h1')).toHaveCSS('animation-name', 'none')
  await page.locator('.ce-intro h1').evaluate(async element => {
    await Promise.all(element.getAnimations({ subtree: true }).map(animation => animation.finished))
  })
  expect(await layout()).toEqual(before)
  await expect(page.locator('.ce-intro h1')).toHaveCSS('opacity', '1')
  await expect(page.locator('.ce-headline-wordmark image')).toHaveAttribute('href', '/enter-wordmark.svg')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)

  await expect(page.locator('.ce-entry-section, .ce-brand-statement, .ce-footer')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(960)

  const link = page.getByTestId('for-recruiters')
  await link.focus()
  await link.press('Tab')
  const candidateLink = page.getByTestId('for-candidates')
  await expect(candidateLink).toBeFocused()
  await expect(candidateLink).toHaveCSS('outline-style', 'solid')
  await expect(page.getByRole('navigation').getByTestId('for-recruiters')).toHaveCount(1)
  await expect(page.getByRole('navigation').getByTestId('for-candidates')).toHaveCount(1)
  await expect(page.locator('.ce-intro button')).toHaveCount(0)
  // The approved simple navigation retains its existing text-only login link.
  await expect(page.getByRole('navigation').locator('.ce-login summary')).toHaveText('Log in')
  await expect(page.getByRole('navigation').locator('.ce-login summary')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true, animations: 'disabled' })
})
}

test('reduced motion keeps the simplified landing page static and usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const headline = page.locator('.ce-intro h1')
  await expect(headline).toHaveCSS('animation-name', 'none')
  await expect(headline).toHaveCSS('opacity', '1')
  await expect(page.locator('.ce-masthead .ce-logo')).toHaveCSS('animation-name', 'none')
  const button = page.getByTestId('for-candidates')
  await button.hover()
  await expect(button.locator('svg')).toHaveCount(0)
  await expect(page.locator('.ce-brand-statement')).toHaveCount(0)
  await button.click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await expect(page.getByText('CANDIDATE PROFILE', { exact: true })).toBeVisible()
})

for (const failure of ['missing', 'throws', 'never calls back']) {
  test(`content and navigation remain usable when IntersectionObserver ${failure}`, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(mode => {
      Object.defineProperty(window, 'IntersectionObserver', {
        configurable: true,
        value: mode === 'missing' ? undefined : class {
          constructor() { if (mode === 'throws') throw new Error('Observer unavailable') }
          observe() {}
          unobserve() {}
          disconnect() {}
        },
      })
    }, failure)
    await page.goto('/')
    await expect(page.getByTestId('for-recruiters')).toBeVisible()
    await expect(page.locator('.ce-intro h1')).toBeVisible()
    await page.getByTestId('for-recruiters').click()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await expect(page.getByLabel('Company')).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
