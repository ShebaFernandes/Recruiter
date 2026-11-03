import { test, expect } from '@playwright/test'
import type { Candidate } from '../src/types'
const profile = {
  id: 9001, full_name: 'Jordan Taylor', headline: 'Senior Platform Engineer',
  current_company: 'Example Studio', email: 'jordan@example.test', phone: '',
  location: 'Bengaluru', total_experience: '8.0', notice_period_days: 30,
  current_salary_lpa: '20.00', expected_salary_lpa: '30.00', employment_type: 'Full-time',
  linkedin_url: '', github_url: '', summary: '', meaningful_work: 'A reliable service that helps teams work together.',
  visibility: 'approved_recruiters', work_preferences: ['Hybrid'], skills: ['Agentic AI', 'LangGraph', 'Redis', 'Generative AI', 'Distributed Systems'],
  education: ['B.Tech, Example University'], profile_status: 'submitted', profile_updated_at: '2026-10-01T00:00:00Z',
  build_lead_preference: 50, profile_photo_url: null, submission_missing_fields: [], missing_fields: [], can_submit: true,
  career_preferences: { availability: 'Open to the right opportunity', preferred_locations: ['Bengaluru'], contact_preferences: ['Email'], standout_signal: 'Built a reliable service for internal teams.', motivators: ['Exceptional team'] },
  work_experiences: [
    { id: 1, company: 'Sample Labs', role: 'Engineer', start_date: '2018-01-01', end_date: '2019-12-31', description: 'Built internal tools.', gap_reason: '' },
    { id: 2, company: 'Example Studio', role: 'Senior Platform Engineer', start_date: '2020-01-01', end_date: null, description: 'Built reliable services.', gap_reason: '' },
  ],
  latest_resume: { id: 1, original_name: 'Jordan-Taylor.docx', version: 1, uploaded_at: '2026-10-01T00:00:00Z', processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false, url: '/api/v1/resumes/1/download/' },
} as Candidate
for (const width of [1440, 390]) test(`opportunity CV review and confirmation at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  let applications = 0
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } })
    if (path.includes('opportunities') && route.request().method() === 'POST') {
      applications++
      expect(route.request().postDataJSON().opportunity_id).toBe('lead-product-manager-consumer')
      return route.fulfill({ status: 201, json: { id: 1, detail: 'Your application has been received.' } })
    }
    if (path.endsWith('/legal/documents/')) return route.fulfill({ json: { enabled: false } })
    return route.fulfill({ json: profile })
  })
  await page.goto('/opportunities?role=lead-product-manager-consumer')
  await page.getByRole('button', { name: 'Apply now', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Choose your CV' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(page.locator('.opportunity-application-page')).toHaveCSS('background-color', 'rgb(250, 248, 244)')
  await expect(page.locator('.opp-application-shell h1')).toHaveCSS('font-family', /Newsreader/)
  await expect(page.locator('.platform-background')).toHaveCount(0)
  await page.screenshot({ path: `/private/tmp/opportunity-cv-${width}.png` })
  await page.getByRole('button', { name: 'Use current CV' }).click()
  await expect(page.getByRole('heading', { name: /Prepare your application/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Review application', exact: true })).toBeEnabled()
  await page.screenshot({ path: `/private/tmp/opportunity-profile-${width}.png` })
  expect(applications).toBe(0)
  await page.getByRole('button', { name: 'Review application', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Submit application', exact: true })).toBeDisabled()
  await page.getByRole('checkbox', { name: /I have reviewed my CV/ }).check()
  await page.screenshot({ path: `/private/tmp/opportunity-confirm-${width}.png` })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Submit application', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your application has been received.' })).toBeVisible()
  expect(applications).toBe(1)
  await page.screenshot({ path: `/private/tmp/opportunity-success-${width}.png` })
})
for (const width of [1440, 390]) test(`new candidate uploads CV before review at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  let uploaded = false
  let applications = 0
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } })
    if (path.endsWith('/legal/documents/')) return route.fulfill({ json: { enabled: false } })
    if (path.endsWith('/candidate/resumes/') && route.request().method() === 'POST') {
      uploaded = true
      return route.fulfill({ status: 202, json: { ...profile, profile_status: 'draft', latest_resume: { ...profile.latest_resume, processing_status: 'queued', scan_status: 'quarantined' } } })
    }
    if (path.endsWith('/candidate/resume-status/')) return route.fulfill({ json: { resume: profile.latest_resume, worker_available: true } })
    if (path.includes('opportunities') && route.request().method() === 'POST') applications++
    return route.fulfill({ json: { ...profile, profile_status: 'draft', latest_resume: uploaded ? profile.latest_resume : null } })
  })
  await page.goto('/opportunities?role=lead-product-manager-consumer')
  await page.getByRole('button', { name: 'Apply now', exact: true }).click()
  const upload = page.getByLabel('Upload your CV', { exact: true })
  await expect(upload).toBeVisible()
  await page.screenshot({ path: `/private/tmp/opportunity-new-cv-${width}.png` })
  await expect(page.getByRole('button', { name: 'Use current CV' })).toHaveCount(0)
  await upload.setInputFiles({ name: 'Jordan-Taylor.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: Buffer.from('Synthetic browser upload fixture') })
  await expect(page.getByRole('heading', { name: /Prepare your application/ })).toBeVisible()
  await expect(page.getByText("Here's how we understand you.", { exact: true })).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('button', { name: 'Review application', exact: true })).toBeDisabled()
  expect(uploaded).toBe(true)
  expect(applications).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const width of [1440, 390]) test(`candidate login retains the existing background at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.route('**/api/v1/**', route => route.fulfill({ status: 401, json: { detail: 'Authentication required.' } }))
  await page.goto('/opportunities?role=backend-engineer')
  await page.getByRole('button', { name: 'Apply now', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back', exact: true })).toBeVisible()
  await expect(page.locator('.platform-background')).toHaveCount(1)
  await expect(page.locator('.opportunity-application-page')).toHaveCount(0)
  await page.screenshot({ path: `/private/tmp/opportunity-login-${width}.png` })
})
