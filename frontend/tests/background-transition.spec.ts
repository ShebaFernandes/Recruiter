import { expect, test } from '@playwright/test'

test('production entry HTML revalidates while retaining CSP', async ({ request }) => {
  test.skip(process.env.PRODUCTION_CSP_TEST !== 'true', 'Requires production nginx')
  for (const path of ['/', '/index.html', '/candidate']) {
    const response = await request.get(path)
    expect(response.status()).toBe(200)
    expect(response.headers()['cache-control']).toContain('no-cache')
    expect(response.headers()['content-security-policy']).toContain("media-src 'self' https://d8j0ntlcm91z4.cloudfront.net")
  }
})

for (const width of [390, 768, 1024, 1440]) {
  test(`first candidate frames retain scenery and full-opacity form at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
    // Hold video unavailable: a ready DOM with no painted scenery must not pass.
    await page.route('**/*.mp4', route => route.abort())
    await page.goto('/')
    await page.getByTestId('for-candidates').waitFor()
    await page.evaluate(() => {
      const samples: { poster: boolean; opacity: number; animations: string[] }[] = []
      Object.assign(window, { backgroundTransitionSamples: samples })
      const sample = () => {
        const background = document.querySelector('.platform-background')
        const form = document.querySelector('.auth-card')
        if (background && form) {
          let opacity = 1
          const animations: string[] = []
          for (let node: Element | null = form; node; node = node.parentElement) {
            const style = getComputedStyle(node)
            opacity *= Number(style.opacity)
            if (style.animationName !== 'none') animations.push(style.animationName)
          }
          samples.push({ poster: getComputedStyle(background).backgroundImage.includes('data:image/jpeg'), opacity, animations })
        }
        if (samples.length < 30) requestAnimationFrame(sample)
      }
      requestAnimationFrame(sample)
    })
    await page.getByTestId('for-candidates').click()
    await page.waitForFunction(() => (window as unknown as { backgroundTransitionSamples: unknown[] }).backgroundTransitionSamples.length >= 30)
    const samples = await page.evaluate(() => (window as unknown as { backgroundTransitionSamples: { poster: boolean; opacity: number; animations: string[] }[] }).backgroundTransitionSamples)
    await info.attach('first-frames', { body: JSON.stringify(samples), contentType: 'application/json' })
    await page.screenshot({ path: info.outputPath('poster-with-video-unavailable.png') })
    expect(samples.every(frame => frame.poster)).toBe(true)
    expect(Math.min(...samples.map(frame => frame.opacity))).toBe(1)
    expect(samples.every(frame => frame.animations.length === 0)).toBe(true)
    await expect(page.getByLabel('Email', { exact: true })).toBeVisible()
  })
}
