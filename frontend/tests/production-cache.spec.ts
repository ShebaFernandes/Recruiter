import { expect, test } from '@playwright/test'

// Run against the real production nginx configuration, never the Vite server.
test.skip(process.env.PRODUCTION_CACHE_TEST !== 'true', 'Requires production nginx')

function expectSecurityHeaders(headers: Record<string, string>) {
  expect(headers['content-security-policy']).toContain("script-src 'self'")
  expect(headers['content-security-policy']).toContain("object-src 'none'")
  expect(headers['x-content-type-options']).toBe('nosniff')
  expect(headers['x-frame-options']).toBe('DENY')
}

test('entry HTML and SPA routes revalidate, including conditional responses', async ({ request }) => {
  for (const path of ['/', '/index.html', '/candidate', '/?return=visit']) {
    const response = await request.get(path)
    expect(response.status()).toBe(200)
    expect(response.headers()['cache-control']).toBe('no-cache, max-age=0, must-revalidate')
    expectSecurityHeaders(response.headers())
    const etag = response.headers().etag
    expect(etag).toBeTruthy()
    const unchanged = await request.get(path, { headers: { 'If-None-Match': etag } })
    expect(unchanged.status()).toBe(304)
    expect(unchanged.headers()['cache-control']).toBe('no-cache, max-age=0, must-revalidate')
    expectSecurityHeaders(unchanged.headers())
    const olderRelease = await request.get(path, { headers: { 'If-None-Match': '"older-release"' } })
    expect(olderRelease.status()).toBe(200)
    expect(await olderRelease.text()).toBe(await response.text())
  }
})

test('only existing fingerprinted CSS and JavaScript are immutable', async ({ request }) => {
  const html = await (await request.get('/')).text()
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+\.(?:js|css))"/g)].map(match => match[1])
  expect(assets).toHaveLength(2)
  for (const path of assets) {
    const response = await request.get(path)
    expect(response.status()).toBe(200)
    expect(response.headers()['cache-control']).toBe('public, max-age=31536000, immutable')
    expect(response.headers()['content-type']).not.toContain('text/html')
    expectSecurityHeaders(response.headers())
    const unchanged = await request.get(path, { headers: { 'If-None-Match': response.headers().etag } })
    expect(unchanged.status()).toBe(304)
    expect(unchanged.headers()['cache-control']).toBe('public, max-age=31536000, immutable')
  }
  const unversioned = await request.get('/enter-wordmark.svg')
  expect(unversioned.status()).toBe(200)
  expect(unversioned.headers()['cache-control'] || '').not.toContain('immutable')
})

test('missing release assets and worker scripts cannot return the SPA', async ({ request }) => {
  for (const path of ['/assets/missing-12345678.js', '/assets/missing-12345678.css', '/sw.js', '/service-worker.js']) {
    const response = await request.get(path)
    expect(response.status()).toBe(404)
    expect(response.headers()['cache-control'] || '').not.toContain('immutable')
    expect(await response.text()).not.toContain('<div id="root">')
    expectSecurityHeaders(response.headers())
  }
})

test('landing does not install a service worker or an offline cache', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('for-candidates')).toBeVisible()
  expect(await page.evaluate(async () => ({
    registrations: (await navigator.serviceWorker.getRegistrations()).length,
    controlled: navigator.serviceWorker.controller !== null,
    caches: await caches.keys(),
  }))).toEqual({ registrations: 0, controlled: false, caches: [] })
})
