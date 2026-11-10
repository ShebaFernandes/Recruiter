import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_AUTOSIGNUP !== '1', 'Requires disposable synthetic signup fixture; never a real provider test')
const api = 'http://127.0.0.1:18012/api/v1'

async function chooseGoogle(page: import('@playwright/test').Page, tag: string) {
  await page.route('https://accounts.google.com/o/oauth2/v2/auth**', async route => {
    const query = new URL(route.request().url()).searchParams
    expect(query.get('prompt')).toBe('select_account')
    expect(query.get('code_challenge_method')).toBe('S256')
    expect(query.get('scope')).toBe('openid email profile')
    const callback = new URL(query.get('redirect_uri')!)
    callback.searchParams.set('state', query.get('state')!)
    callback.searchParams.set('code', `synthetic-browser-${tag}`)
    await route.fulfill({ status: 302, headers: { location: callback.href } })
  })
}

async function openSignup(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled()
  await expect(page.getByText(/These are your declarations; Google sign-in does not verify/)).toBeVisible()
  await expect(page.locator('.google-login input')).toHaveCount(0)
}

test('single-button signup opens My Profile and repeat login keeps the same account', async ({ page }) => {
  await chooseGoogle(page, 'profile')
  await openSignup(page)
  const terms = page.locator('.google-login').getByRole('link', { name: 'Terms', exact: true })
  expect((await page.request.get((await terms.getAttribute('href'))!)).status()).toBe(200)
  await page.screenshot({ path: '/private/tmp/enter-google-approved-notice-synthetic.png', fullPage: false })
  await page.getByRole('button', { name: 'Continue with Google' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.locator('.candidate-experience')).toBeVisible()
  const original = await (await page.request.get(api + '/auth/me/')).json()
  expect(original.has_password).toBe(false)
  await expect(page.getByText('Complete your candidate account', { exact: true })).toHaveCount(0)
  await page.screenshot({ path: '/private/tmp/enter-google-automatic-profile-synthetic.png', fullPage: false })
  await page.getByRole('button', { name: /Synthetic Browser Candidate/ }).click()
  const signedOut = page.waitForResponse(response => response.url().endsWith('/auth/logout/') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Log Out', exact: true }).click()
  expect((await signedOut).ok()).toBe(true)
  await expect(page.getByRole('button', { name: 'Join enter’s Talent network', exact: true })).toBeVisible()
  await openSignup(page)
  await page.getByRole('button', { name: 'Continue with Google' }).click()
  await expect(page.locator('.candidate-experience')).toBeVisible()
  const again = await (await page.request.get(api + '/auth/me/')).json()
  expect(again.id).toBe(original.id)
})

test('automatic signup preserves Apply intent without submitting', async ({ page }) => {
  await chooseGoogle(page, 'application')
  let submissions = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/opportunities/applications/')) submissions++ })
  await page.goto('/opportunities?role=backend-engineer')
  await page.getByRole('button', { name: 'Apply now', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled()
  await page.getByRole('button', { name: 'Continue with Google' }).click()
  await expect(page).toHaveURL(/\/opportunities\?role=backend-engineer&apply=1/)
  await expect(page.getByRole('heading', { name: 'Start with your CV' })).toBeVisible()
  expect(submissions).toBe(0)
})
