import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

function localWorker(script: string) {
  if (!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || '') || process.env.RESUME_AI_ENABLED !== 'false') throw new Error('Requires isolated offline E2E environment')
  const result = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
${script}`], { cwd: path.resolve('../backend'), env: process.env, encoding: 'utf8', timeout: 30000 })
  expect(result.status, 'Offline worker exits cleanly (private diagnostics withheld)').toBe(0)
  return result.stdout.trim()
}

test('failed worker retries the saved upload and returns to My Profile without another upload', async ({ page }, info) => {
  test.setTimeout(90000)
  await page.setViewportSize({ width: 390, height: 900 })
  const email = `worker-retry-${Date.now()}@example.com`
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Asha Rao')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('strong-pass-123')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  let uploads = 0
  page.on('request', request => { if (request.url().endsWith('/candidate/resumes/') && request.method() === 'POST') uploads++ })
  const accepted = page.waitForResponse(response => response.url().endsWith('/candidate/resumes/') && response.status() === 202)
  await page.getByTestId('resume-input').setInputFiles(path.resolve('../backend/tests/fixtures/asha-rao-resume.docx'))
  const resumeId = (await (await accepted).json()).latest_resume.id
  expect(localWorker(`from unittest.mock import patch
from talent.models import ResumeProcessingJob
from talent.worker_runtime import run_bounded_job
job = ResumeProcessingJob.objects.get(resume_id=${resumeId})
job.max_attempts = 1
job.save(update_fields=['max_attempts'])
with patch('talent.worker_runtime.subprocess.run', side_effect=OSError):
    print(run_bounded_job(job.pk))`)).toBe('failed')
  await expect(page.getByRole('heading', { name: 'We couldn’t finish this resume' })).toBeVisible({ timeout: 20000 })
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('failed-mobile.png'), animations: 'disabled' })
  const retryResponse = page.waitForResponse(response => response.url().endsWith(`/resumes/${resumeId}/retry/`))
  await page.getByRole('button', { name: 'Retry processing', exact: true }).click()
  const retry = await retryResponse
  expect(retry.status()).toBe(202)
  expect((await retry.json()).latest_resume.id).toBe(resumeId)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'While we get to know you…' })).toBeVisible()
  expect(localWorker(`from talent.models import ResumeProcessingJob, ResumeAIUsage
from talent.worker_runtime import run_bounded_job
assert run_bounded_job(${resumeId}) == 'completed'
job = ResumeProcessingJob.objects.get(resume_id=${resumeId})
assert ResumeProcessingJob.objects.filter(resume_id=${resumeId}).count() == 1
assert ResumeAIUsage.objects.filter(resume_id=${resumeId}).count() == 0
print(job.state)`)).toBe('completed')
  await expect(page.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible({ timeout: 20000 })
  expect(uploads).toBe(1)
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('retry-completed-mobile.png'), animations: 'disabled' })
})
