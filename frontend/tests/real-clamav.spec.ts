import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test.skip(process.env.E2E_REAL_CLAMAV !== '1', 'Requires a loopback-only disposable ClamAV service')
const api = process.env.PLAYWRIGHT_API_URL
const python = path.resolve('../.venv/bin/python')

async function candidate(page: Page) {
  const email = `scanner-${Date.now()}@example.test`
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Scanner Test Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Scanner-test-password-123!')
  const legal = page.getByRole('checkbox', { name: /at least 18 years old.*Terms of Use/i })
  if (await legal.count()) await legal.check()
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
  return email
}

function fictionalFiles(info: TestInfo, email: string) {
  const pdf = info.outputPath('fictional.pdf')
  const docx = info.outputPath('fictional.docx')
  const infected = info.outputPath('eicar-test.docx')
  const result = spawnSync(python, ['-c', `import django; django.setup()
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from docx import Document
from tests.test_candidate_flow import resume_pdf
lines = ['Name: Scanner Test Candidate', 'Email: ${email}', 'Role: Backend Engineer',
         'Work Experience', 'Experience: Backend Engineer|Fictional Systems|2022-01-01|Present|Built APIs',
         'Experience: Software Engineer|Example Labs|2020-01-01|2021-12-01|Built services']
Path(${JSON.stringify(pdf)}).write_bytes(resume_pdf(lines))
document = Document()
for line in lines: document.add_paragraph(line)
output = BytesIO(); document.save(output)
Path(${JSON.stringify(docx)}).write_bytes(output.getvalue())
eicar = bytes.fromhex('58354f2150254041505b345c505a58353428505e2937434329377d2445494341522d5354414e444152442d414e544956495255532d544553542d46494c452124482b482a')
with ZipFile(${JSON.stringify(infected)}, 'w') as archive:
    with ZipFile(BytesIO(output.getvalue())) as original:
        for item in original.infolist(): archive.writestr(item, original.read(item.filename))
    archive.writestr('word/embeddings/eicar.com', eicar)
`], { cwd: path.resolve('../backend'), env: { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings' }, encoding: 'utf8' })
  expect(result.status, result.stderr).toBe(0)
  return { pdf, docx, infected }
}

async function upload(page: Page, file: string) {
  const response = page.waitForResponse(result => result.url().endsWith('/candidate/resumes/') && result.request().method() === 'POST')
  await page.getByTestId('resume-input').setInputFiles(file)
  const accepted = await response
  expect(accepted.status()).toBe(202)
  return (await accepted.json()).latest_resume.id as number
}

async function profile(page: Page) {
  const response = await page.request.get(`${api}/candidate/profile/`)
  expect(response.status()).toBe(200)
  return response.json()
}

test('real ClamAV and worker accept fictional PDF/DOCX and reject EICAR', async ({ page }, info) => {
  test.setTimeout(120_000)
  const files = fictionalFiles(info, await candidate(page))
  for (const file of [files.pdf, files.docx]) {
    const resumeId = await upload(page, file)
    await expect.poll(async () => (await profile(page)).latest_resume.processing_status, { timeout: 60_000 }).toBe('completed')
    const saved = await profile(page)
    expect(saved.latest_resume.id).toBe(resumeId)
    expect(saved.latest_resume.scan_status).toBe('clean')
    expect(saved.employment_extraction.source).toBe('rules')
    expect(saved.work_experiences).toHaveLength(2)
    await expect(page.locator('.career-period')).toHaveCount(2)
  }
  const before = (await profile(page)).work_experiences
  const infectedId = await upload(page, files.infected)
  await expect.poll(async () => (await profile(page)).latest_resume.scan_status, { timeout: 60_000 }).toBe('infected')
  const after = await profile(page)
  expect(after.latest_resume.id).toBe(infectedId)
  expect(after.latest_resume.processing_status).toBe('failed')
  expect(after.work_experiences).toEqual(before)
  expect((await page.request.get(`${api}/resumes/${infectedId}/download/`)).status()).not.toBe(200)
})

test('scanner outage leaves a fictional upload quarantined without profile changes', async ({ page }, info) => {
  test.setTimeout(60_000)
  if (!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || '')) throw new Error('Disposable database required')
  const files = fictionalFiles(info, await candidate(page))
  const resumeId = await upload(page, files.pdf)
  await expect.poll(() => {
    const result = spawnSync(python, ['-c', `import django; django.setup()
from talent.models import ResumeProcessingJob
print(ResumeProcessingJob.objects.get(resume_id=${resumeId}).attempts)`],
    { cwd: path.resolve('../backend'), env: { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings' }, encoding: 'utf8' })
    expect(result.status).toBe(0)
    return Number(result.stdout.trim())
  }, { timeout: 25_000 }).toBeGreaterThan(0)
  const saved = await profile(page)
  expect(saved.latest_resume.scan_status).not.toBe('clean')
  expect(saved.latest_resume.processing_status).not.toBe('completed')
  expect(saved.work_experiences).toHaveLength(0)
  expect((await page.request.get(`${api}/resumes/${resumeId}/download/`)).status()).not.toBe(200)
})
