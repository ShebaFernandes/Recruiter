import { expect, test } from '@playwright/test'

for (const width of [390, 1440]) test(`zero-role recovery is clear at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let retried = false
  const resume = { id: 41, original_name: 'fictional.pdf', version: 1,
    uploaded_at: '2026-10-27T10:00:00Z', processing_status: 'completed', scan_status: 'clean',
    processing_error: '', can_retry: true, url: '/api/v1/resumes/41/download/' }
  const profile = () => ({ id: 9001, full_name: 'Fictional Candidate', email: 'fictional@example.test',
    headline: '', current_company: '', total_experience: null, skills: [], education: [],
    work_preferences: [], work_experiences: [], notice_period_days: null,
    career_preferences: {}, meaningful_work: '', submission_missing_fields: [], can_submit: false,
    profile_status: 'draft', visibility: '',
    latest_resume: retried ? { ...resume, processing_status: 'queued', can_retry: false } : resume,
    employment_extraction: retried ? { resume_id: 41, status: 'processing', source: 'unknown',
      reason_code: 'latest_resume_processing', accepted_role_count: 0, saved_role_count: 0,
      profile_state: 'unchanged', stale_profile_preserved: false } : {
      resume_id: 41, status: 'review_required', source: 'ai', reason_code: 'ai_no_supported_roles',
      accepted_role_count: 0, saved_role_count: 0, profile_state: 'empty',
      stale_profile_preserved: false },
  })
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, role: 'candidate', full_name: 'Fictional Candidate', email: 'fictional@example.test' } })
    if (path.endsWith('/candidate/profile/')) return route.fulfill({ json: profile() })
    if (path.endsWith('/candidate/resumes/41/retry/')) {
      retried = true
      return route.fulfill({ status: 202, json: profile() })
    }
    if (path.endsWith('/candidate/resume-status/')) return route.fulfill({ json: { resume: profile().latest_resume, worker_available: true } })
    return route.fulfill({ json: {} })
  })
  await page.route('**/*.mp4', route => route.abort())
  await page.goto('/')
  await expect(page.getByText('It may still contain jobs; your resume is saved')).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'It may still contain jobs' })).toBeVisible()
  const retry = page.getByRole('button', { name: 'Try reading this saved resume again (without AI)' })
  await expect(retry).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath(`zero-role-${width}.png`), fullPage: true })
  await retry.click()
  await expect.poll(() => retried).toBe(true)
})
