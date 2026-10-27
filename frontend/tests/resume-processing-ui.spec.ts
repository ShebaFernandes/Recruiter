import { expect, test } from '@playwright/test'
import { spawn, spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

// Real local uploads and extraction. Only test-worker latency is controlled so
// scanning/processing can be observed; no application delays or fake job states.
test.use({ video: 'on', actionTimeout: 15_000 })
test.setTimeout(240_000)
const backend = path.resolve('../backend')
const python = path.resolve('../.venv/bin/python')
function worker(resumeId: number, slow = true) {
  if (!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || '') || process.env.AI_PROVIDER !== 'deterministic') throw new Error('Use the isolated offline candidate E2E environment.')
  const script = `import os, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from talent import resume_processing as processing
from talent.models import ResumeProcessingJob
from talent.worker_runtime import heartbeat
heartbeat('observed-test-worker', 'processing')
original_parse = processing.parse_resume
class ObservedScanner(processing.DevelopmentResumeScanner):
    def scan(self, file):
        time.sleep(${slow ? 18 : 0})
        return super().scan(file)
def observed_parse(file, name):
    time.sleep(${slow ? 10 : 0})
    return original_parse(file, name)
processing.get_resume_scanner = lambda: ObservedScanner()
processing.parse_resume = observed_parse
job = ResumeProcessingJob.objects.get(resume_id=${resumeId})
if ${slow ? 'True' : 'False'}:
    print(processing.process_resume_job(job.pk, str(job.idempotency_key)))
else:
    from talent.worker_runtime import run_bounded_job
    print(run_bounded_job(job.pk))
heartbeat('observed-test-worker', 'stopped')`
  const child = spawn(python, ['-c', script], { cwd: backend, env: process.env })
  let output = ''
  child.stdout.on('data', data => { output += data.toString() })
  // Do not echo document contents or worker tracebacks into browser reports.
  child.stderr.resume()
  return { child, done: new Promise<string>((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', code => code === 0 ? resolve(output.trim()) : reject(new Error(`Local test worker exited ${code}`)))
  }) }
}

for (const width of [1440, 390]) test(`accepted uploads and replacements visibly process at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  const email = `processing-ui-${width}-${Date.now()}@example.com`
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Processing Test Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('strong-pass-123')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  const docx = info.outputPath('fictional.docx'), pdf = info.outputPath('fictional.pdf')
  const careerUpdate = info.outputPath('career-update.docx')
  const otherPerson = info.outputPath('other-person.pdf')
  const fixture = spawnSync(python, ['-c', `import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from pathlib import Path
from tests.test_candidate_flow import resume_pdf, resume_docx
from talent.worker_runtime import heartbeat
heartbeat('observed-test-worker', 'stopped')
Path(${JSON.stringify(docx)}).write_bytes(resume_docx())
Path(${JSON.stringify(pdf)}).write_bytes(resume_pdf(['Name: Asha Rao', 'Role: Principal Engineer', 'Location: Pune', 'Skills: Python, Django']))
Path(${JSON.stringify(otherPerson)}).write_bytes(resume_pdf())
Path(${JSON.stringify(careerUpdate)}).write_bytes(resume_docx(role='Staff Engineer', extra='Experience: Advisor|New Studio|2025-01-01|Present|Advises engineers'))`], { cwd: backend, env: process.env })
  expect(fixture.status).toBe(0)
  const heading = page.getByRole('heading', { name: "While we get to know you…" })
  const state = page.locator('.cp-processing-status')
  for (const [index, file] of [docx, pdf].entries()) {
    if (index) {
      await page.getByRole('button', { name: 'Not quite — edit', exact: true }).click()
      await page.getByLabel('Professional title', { exact: true }).fill('Candidate-corrected title')
      await page.getByRole('button', { name: 'Save corrections' }).click()
      await expect(page.locator('.cp-identity')).toContainText('Candidate-corrected title')
      await page.getByTestId('resume-input').scrollIntoViewIfNeeded()
    }
    const upload = page.waitForResponse(r => r.url().endsWith('/candidate/resumes/') && r.request().method() === 'POST')
    await page.getByTestId('resume-input').setInputFiles(file)
    const response = await upload
    expect(response.status()).toBe(202)
    const accepted = await response.json()
    await expect(heading).toBeInViewport()
    await expect(state).toContainText('Queued')
    await expect(page.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (!index) {
      const bar = page.locator('.cp-processing-bar span')
      const first = await bar.evaluate(el => getComputedStyle(el).transform)
      await expect.poll(() => bar.evaluate(el => getComputedStyle(el).transform)).not.toBe(first)
      // No worker exists yet: the new health status must pause decorative progress,
      // not keep implying that resume extraction is underway.
      await expect(state).toContainText('temporarily delayed', { timeout: 20_000 })
      await expect(page.locator('.cp-processing-bar')).toHaveClass(/is-paused/)
      await expect(page.locator('.cp-processing-prompts li')).toHaveCount(4)
      await expect(page.locator('.cp-processing-prompts input')).toHaveCount(0)
      await expect(bar).toHaveCSS('height', '6px')
      await page.screenshot({ path: info.outputPath(`queued-${width}.png`) })
      // A disconnected status poll must offer recovery without claiming failure.
      await page.route('**/candidate/resume-status/', route => route.abort())
      await expect(state).toContainText('Unable to check', { timeout: 20_000 })
      await expect(page.getByRole('button', { name: 'Check status again' })).toBeVisible()
      await page.unroute('**/candidate/resume-status/')
      await page.getByRole('button', { name: 'Check status again' }).click()
      await expect(state).toContainText('temporarily delayed')
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await expect(bar).toHaveCSS('animation-name', 'none')
      await page.emulateMedia({ reducedMotion: 'no-preference' })
    }
    const running = worker(accepted.latest_resume.id)
    try {
      await expect(state).toContainText('Scanning', { timeout: 20_000 })
      await page.screenshot({ path: info.outputPath(`scanning-${index}-${width}.png`) })
      if (!index) {
        await page.reload()
        await expect(heading).toBeVisible()
        await expect(state).toContainText(/Scanning|Extracting/)
      }
      await expect(state).toContainText('Extracting', { timeout: 40_000 })
      await page.screenshot({ path: info.outputPath(`processing-${index}-${width}.png`) })
      expect(await running.done).toBe('completed')
      await expect(heading).toHaveCount(0, { timeout: 20_000 })
      await expect(page.locator('.cp-identity')).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Review resume changes' })).toHaveCount(0)
      await page.screenshot({ path: info.outputPath(`my-profile-${index}-${width}.png`) })
      if (index) {
        await expect(page.getByRole('heading', { name: "Here's how we understand you.", exact: true })).toBeInViewport()
        await expect(page.getByRole('heading', { name: 'Review resume changes' })).toHaveCount(0)
        await expect(page.locator('.cp-resume-updates')).not.toHaveAttribute('open')
        await expect(page.locator('.cp-identity')).toContainText('Candidate-corrected title')
        // Leave the conflict pending; a subsequent upload must not silently discard it.
      }
    } finally { if (running.child.exitCode === null) running.child.kill() }
  }
  // Unmodified-speed worker: a fast job must not wait for the message cycle.
  await expect(page.getByTestId('resume-input')).toBeEnabled()
  const fastUpload = page.waitForResponse(r => r.url().endsWith('/candidate/resumes/') && r.request().method() === 'POST')
  await page.getByTestId('resume-input').setInputFiles(careerUpdate)
  const fast = worker((await (await fastUpload).json()).latest_resume.id, false)
  expect(await fast.done).toBe('completed')
  await expect(page.getByRole('heading', { name: "Here's how we understand you.", exact: true })).toBeInViewport({ timeout: 20_000 })
  await expect(page.getByRole('heading', { name: 'Review resume changes' })).toHaveCount(0)
  await expect(page.locator('.cp-resume-updates')).not.toHaveAttribute('open')
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Advisor at New Studio/ })).toBeVisible()
  await expect(page.locator('.career-journey .career-period')).toHaveCount(3)
  const saved = await (await page.request.get(`${process.env.PLAYWRIGHT_API_URL}/candidate/profile/`)).json()
  expect(saved.work_experiences).toHaveLength(3)
  await expect(page.locator('.cp-identity')).toContainText('Candidate-corrected title')
  await page.screenshot({ path: info.outputPath(`my-profile-safe-update-${width}.png`) })
  await page.getByRole('button', { name: 'View Resume', exact: true }).click()
  await expect(page.locator('.cp-docx')).toContainText('New Studio')
  const mismatchUpload = page.waitForResponse(r => r.url().endsWith('/candidate/resumes/') && r.request().method() === 'POST')
  await page.getByTestId('resume-input').setInputFiles(otherPerson)
  const mismatch = worker((await (await mismatchUpload).json()).latest_resume.id, false)
  expect(await mismatch.done).toBe('completed')
  await expect(page.getByRole('alert').filter({ hasText: "We couldn't match this resume" })).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('.cp-identity')).toContainText('Asha Rao')
  await expect(page.locator('.cp-identity')).toContainText('Candidate-corrected title')
  await expect(page.locator('.career-journey .career-period')).toHaveCount(3)
  await expect(page.locator('.career-sequence.needs-review')).toHaveCount(3)
  await expect(page.getByRole('heading', { name: 'Review resume changes' })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath(`identity-protected-${width}.png`) })
  await page.getByRole('button', { name: 'View Resume', exact: true }).click()
  await expect(page.locator('iframe[title="Original PDF resume"]')).toHaveAttribute('src', /^blob:/)
  const afterMismatch = await (await page.request.get(`${process.env.PLAYWRIGHT_API_URL}/candidate/profile/`)).json()
  expect(afterMismatch.work_experiences).toEqual(saved.work_experiences)
  expect(afterMismatch.career_preferences).toEqual(saved.career_preferences)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
