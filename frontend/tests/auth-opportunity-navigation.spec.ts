import { expect, test } from '@playwright/test'

test.skip(process.env.E2E_AUTH_NAVIGATION !== '1', 'Requires isolated synthetic local test servers')
const api = process.env.E2E_API_URL || 'http://127.0.0.1:18011/api/v1'
const email = 'navigation-synthetic@example.test'
const password = 'Synthetic-navigation-password-123!'

async function session(page: import('@playwright/test').Page) {
  const csrf = await (await page.request.get(`${api}/auth/csrf/`)).json()
  const result = await page.request.post(`${api}/auth/login/`, {
    data: { email, password }, headers: { 'X-CSRFToken': csrf.csrfToken },
  })
  expect(result.status()).toBe(200)
}

test('public browsing, search and job descriptions do not require authentication', async ({ page }) => {
  await page.goto('/opportunities')
  await expect(page.getByRole('searchbox', { name: 'Search opportunities' })).toBeVisible()
  await page.getByRole('searchbox', { name: 'Search opportunities' }).fill('Backend')
  await page.getByRole('combobox', { name: 'Location', exact: true }).selectOption('Remote')
  await page.getByRole('button', { name: 'View Opportunity', exact: true }).first().click()
  await expect(page.getByRole('dialog', { name: 'Job description' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toHaveCount(0)
  for (const path of ['/candidate/profile/', '/opportunities/applications/', '/resumes/123/download/']) {
    const result = await page.request.get(api + path)
    expect([401, 403, 404]).toContain(result.status())
  }
  await page.screenshot({ path: '/private/tmp/enter-public-opportunities-review.png', fullPage: false, animations: 'disabled' })
})

test('Apply preserves intent through password login and never submits automatically', async ({ page }) => {
  let submitted = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/opportunities/applications/')) submitted++ })
  await page.route('**/auth/google/config/', route => route.fulfill({ json: { enabled: true } }))
  await page.goto('/opportunities?role=backend-engineer')
  await page.getByRole('button', { name: 'Apply now', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled()
  await page.getByText('Continue with email', { exact: true }).click()
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page).toHaveURL(/\/opportunities\?role=backend-engineer&apply=1/)
  await expect(page.getByRole('heading', { name: 'Start with your CV' })).toBeVisible()
  expect(submitted).toBe(0)
  await page.screenshot({ path: '/private/tmp/enter-restored-application-review.png', fullPage: false })
})

test('incomplete Google-session landing opens My Profile and still permits browsing', async ({ page }) => {
  // Isolate redirect behavior: establish a synthetic session through existing password auth.
  // Google protocol verification is exercised by backend OAuth tests, not this browser fixture.
  await session(page)
  await page.goto('/auth/google?result=success&next=%2F')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.locator('.candidate-experience')).toBeVisible()
  await page.getByRole('button', { name: 'Opportunities', exact: true }).click()
  await expect(page.getByRole('searchbox', { name: 'Search opportunities' })).toBeVisible()
})

test('completed Google-session landing opens Opportunities using existing readiness rules', async ({ page }) => {
  await session(page)
  await page.route('**/candidate/profile/', async route => {
    const response = await route.fetch()
    const profile = await response.json()
    await route.fulfill({ json: { ...profile, profile_status: 'submitted', can_submit: true,
      resume_identity_warning: null, resume_review: null,
      latest_resume: { id: 9, processing_status: 'completed', scan_status: 'clean' } } })
  })
  await page.goto('/auth/google?result=success&next=%2F')
  await expect(page).toHaveURL(/\/opportunities$/)
  await expect(page.getByRole('searchbox', { name: 'Search opportunities' })).toBeVisible()
})


test('Google-session intent resumes the chosen application without posting it', async ({ page }) => {
  let submitted = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/opportunities/applications/')) submitted++ })
  await session(page)
  await page.goto('/auth/google?result=success&next=' + encodeURIComponent('/opportunities?role=backend-engineer&apply=1'))
  await expect(page).toHaveURL(/\/opportunities\?role=backend-engineer&apply=1/)
  await expect(page.getByRole('heading', { name: 'Start with your CV' })).toBeVisible()
  expect(submitted).toBe(0)
})

test('unapproved signup cannot create an account and still permits public browsing', async ({ page }) => {
  await page.route('**/auth/google/pending/', route => route.fulfill({ json: {
    stage: 'signup', email: 'pending-synthetic@example.test', full_name: 'Synthetic Pending', signup_available: false,
  } }))
  await page.goto('/auth/google?result=signup')
  await expect(page.getByRole('heading', { name: 'Google signup is not available yet' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create candidate account' })).toHaveCount(0)
  await expect(page.getByRole('checkbox')).toHaveCount(0)
  const csrf = await (await page.request.get(`${api}/auth/csrf/`)).json()
  const result = await page.request.post(`${api}/auth/google/complete/`, {
    data: { country_code: 'IN', age_accepted: true, terms_accepted: true, terms_version: 'unapproved-draft', age_version: 'unapproved-draft' },
    headers: { 'X-CSRFToken': csrf.csrfToken },
  })
  expect(result.status()).toBe(503)
  expect((await result.json()).code).toBe('signup_requirements_unavailable')
  await page.getByRole('link', { name: 'Browse Opportunities', exact: true }).click()
  await expect(page.getByRole('searchbox', { name: 'Search opportunities' })).toBeVisible()
})
