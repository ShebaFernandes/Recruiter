import { expect, test } from '@playwright/test'

// Run against a production build served by frontend/nginx.conf, not Vite.
test.skip(process.env.PRODUCTION_CSP_TEST !== 'true', 'Requires production nginx')

test('production CSP permits only the approved video origin and playback works', async ({ page }) => {
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
  const response = await page.goto('/')
  const policy = response!.headers()['content-security-policy']
  expect(policy).toContain("media-src 'self' https://d8j0ntlcm91z4.cloudfront.net;")
  expect(policy).toContain("connect-src 'self'")
  expect(policy).toContain("script-src 'self'")
  expect(policy).toContain("object-src 'none'")
  expect(policy).not.toContain('*')
  await page.getByTestId('for-candidates').click()
  const video = page.locator('.platform-background video')
  await expect(video).toHaveJSProperty('muted', true)
  await expect(video).toHaveCSS('object-fit', 'cover')
  await expect(video).toHaveCSS('object-position', '50% 100%')
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => el.currentTime), { timeout: 30000 }).toBeGreaterThan(0.2)
  const time = await video.evaluate((el: HTMLVideoElement) => el.currentTime)
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => el.currentTime)).toBeGreaterThan(time)
})

test('production reduced-motion preference retains the still fallback', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.locator('.platform-background')).toHaveAttribute('data-render-state', 'fallback')
  await expect(page.locator('.platform-background video')).toHaveCount(0)
  // The existing accessible fallback is a static neutral surface, not a video still.
  await expect(page.locator('.platform-background')).toHaveCSS('background-color', 'rgb(247, 249, 252)')
})
