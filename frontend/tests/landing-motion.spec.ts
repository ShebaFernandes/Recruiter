import { expect, test } from '@playwright/test'

// Exercise the real App now that the authentication stylesheet is available.

for (const width of [1440, 1024, 390]) {
test(`landing motion at ${width}px preserves layout and section reveals run once`, async ({ page }, testInfo) => {
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
  await expect(page.locator('.ce-intro h1')).toHaveCSS('animation-name', 'ce-headline-reveal')
  await page.locator('.ce-intro h1').evaluate(async element => {
    await Promise.all(element.getAnimations({ subtree: true }).map(animation => animation.finished))
  })
  expect(await layout()).toEqual(before)
  await expect(page.locator('.ce-intro h1')).toHaveCSS('opacity', '1')
  expect(await page.locator('.ce-intro h1 em').evaluate(element => getComputedStyle(element, '::after').transform)).toBe('matrix(1, 0, 0, 1, 0, 0)')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)

  const candidate = page.locator('#candidate-entry')
  await candidate.scrollIntoViewIfNeeded()
  await expect(candidate).toHaveClass(/is-revealed/)
  const startTime = await candidate.evaluate(async element => {
    const animation = element.getAnimations()[0]
    await animation.finished
    return animation.startTime
  })
  await page.locator('.ce-masthead').scrollIntoViewIfNeeded()
  await candidate.scrollIntoViewIfNeeded()
  expect(await candidate.evaluate(element => element.getAnimations()[0].startTime)).toBe(startTime)
  const recruiter = page.locator('#recruiter-entry')
  await recruiter.scrollIntoViewIfNeeded()
  await expect(recruiter).toHaveClass(/is-revealed/)
  const action = page.getByTestId('for-recruiters')
  await action.hover()
  await expect(action.locator('svg')).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 3, 0)')

  const link = page.getByRole('navigation').getByRole('link', { name: 'For recruiters' })
  await link.focus()
  await link.press('Tab')
  const candidateLink = page.getByRole('navigation').getByRole('link', { name: 'For candidates' })
  await expect(candidateLink).toBeFocused()
  await expect.poll(() => candidateLink.evaluate(element => getComputedStyle(element, '::after').transform)).toBe('matrix(1, 0, 0, 1, 0, 0)')
  await candidateLink.press('Tab')
  const login = page.locator('.ce-login summary')
  await expect(login).toBeFocused()
  await expect.poll(() => login.evaluate(element => getComputedStyle(element, '::after').transform)).toBe('matrix(1, 0, 0, 1, 0, 0)')
  await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true, animations: 'disabled' })
})
}

test('reduced motion shows the complete landing page with static hover arrows', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const headline = page.locator('.ce-intro h1')
  await expect(headline).toHaveCSS('animation-name', 'none')
  await expect(headline).toHaveCSS('opacity', '1')
  await expect(page.locator('.ce-masthead .ce-logo')).toHaveCSS('animation-name', 'none')
  expect(await page.locator('.ce-intro h1 em').evaluate(element => getComputedStyle(element, '::after').animationName)).toBe('none')
  const button = page.getByTestId('for-candidates')
  await button.hover()
  await expect(button.locator('svg')).toHaveCSS('transform', 'none')
  await expect(page.locator('#candidate-entry')).toHaveCSS('opacity', '1')
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
    await expect(page.locator('#recruiter-entry')).toHaveCSS('opacity', '1')
    await expect(page.locator('#candidate-entry')).toHaveCSS('opacity', '1')
    await page.getByTestId('for-recruiters').click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expect(page.getByLabel('Company')).toBeVisible()
    expect(errors).toEqual([])
  })
}
