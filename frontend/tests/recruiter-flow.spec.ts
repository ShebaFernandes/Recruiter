import { expect, test, type APIRequestContext } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

const API = 'http://127.0.0.1:8010/api/v1'
const password = 'strong-pass-123'

async function seedCandidate(request: APIRequestContext, index: number, runId: number) {
  const people = [
    ['Anika Bose', 'Senior Backend Engineer', 'SignalWorks', '6.2', '30', '28.00'],
    ['Kabir Shah', 'Backend Engineer', 'LedgerFox', '4.8', '15', '24.00'],
    ['Meera Iyer', 'Staff Backend Engineer', 'DataHarbor', '7.1', '45', '34.00'],
    ['Rohan Menon', 'Backend Engineer', 'CloudMint', '5.3', '60', '26.00'],
  ]
  const [baseName, headline, company, experience, notice, salary] = people[index]
  const name = baseName
  const email = `seed-${runId}-${index}@example.com`
  const signup = await request.post(`${API}/auth/signup/`, {
    data: { email, password, full_name: name, role: 'candidate' },
  })
  expect(signup.ok()).toBeTruthy()
  const verificationToken = issueLocalAccountToken(email, 'verify_email')
  const verified = await request.post(`${API}/auth/verify-email/`, {
    data: { token: verificationToken },
  })
  expect(verified.ok()).toBeTruthy()
  const auth = await verified.json()
  const headers = { Authorization: `Token ${auth.token}` }
  const fixture = fs.readFileSync(path.resolve('../backend/tests/fixtures/asha-rao-resume.docx'))
  const upload = await request.post(`${API}/candidate/resumes/`, {
    headers,
    multipart: { file: { name: 'asha-rao-resume.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: fixture } },
  })
  expect(upload.ok()).toBeTruthy()
  const profile = await request.patch(`${API}/candidate/profile/`, {
    headers,
    data: {
      full_name: name, email, headline, current_company: company, location: 'Bengaluru',
      total_experience: experience, notice_period_days: Number(notice),
      expected_salary_lpa: salary, phone: `+9198765432${index}`,
      linkedin_url: `https://linkedin.com/in/test-${runId}-${index}`,
      github_url: `https://github.com/test-${runId}-${index}`,
      summary: `${headline} with production ownership across event-driven products.`,
      meaningful_work: `Built a resilient event platform at ${company}.`,
      visibility: 'approved_recruiters',
      work_preferences: ['Hybrid', 'Remote'],
      skills: index === 2 ? ['Java', 'Kafka', 'AWS', 'PostgreSQL'] : ['Python', 'Django', 'Kafka', 'PostgreSQL'],
      work_experiences: [
        { company: `Early ${company}`, role: 'Software Engineer', start_date: '2018-01-01', end_date: '2020-01-01', description: 'Built APIs.' },
        { company, role: headline, start_date: index === 0 ? '2021-01-01' : '2020-02-01', end_date: null, description: 'Owned reliable backend systems.' },
      ],
    },
  })
  expect(profile.ok()).toBeTruthy()
  const submitted = await request.post(`${API}/candidate/profile/submit/`, {
    headers,
    data: { consent: true },
  })
  expect(submitted.ok()).toBeTruthy()
  return { email, token: auth.token, name }
}

test('recruiter completes clarification, filters, compares, reviews and persists signals', async ({ page, request }) => {
  const runId = Date.now()
  const candidates = []
  for (let index = 0; index < 4; index += 1) candidates.push(await seedCandidate(request, index, runId))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByTestId('for-recruiters').click()
  await page.getByLabel('Full name').fill('Ritu Mehta')
  await page.getByLabel('Company').fill('Enter Labs')
  await page.getByLabel('Email').fill(`recruiter-${runId}@company.example`)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await page.getByRole('button', { name: 'Projects' }).click()
  await page.getByLabel('New project name').fill(`Backend hiring ${runId}`)
  await page.getByRole('button', { name: 'Create project' }).click()
  await expect(page.locator('.workspace-sidepanel').getByText(`Backend hiring ${runId}`)).toBeVisible()
  await page.getByRole('button', { name: 'Projects' }).click()

  const searchBox = await page.locator('.chat-composer').boundingBox()
  expect(searchBox?.width).toBeGreaterThanOrEqual(679)
  expect(searchBox?.width).toBeLessThanOrEqual(681)
  expect(searchBox?.height).toBeGreaterThanOrEqual(57)
  expect(searchBox?.height).toBeLessThanOrEqual(59)

  await page.getByLabel('Candidate search').fill('Backend engineer with 4 years experience')
  await page.getByRole('button', { name: 'Search talent' }).click()
  await expect(page.getByText('One detail before I search')).toBeVisible()
  await expect(page.getByText(/preferred location/)).toBeVisible()
  await page.getByRole('button', { name: 'Bengaluru', exact: true }).click()
  const cards = page.locator('.candidate-card')
  await expect(cards.first()).toBeVisible()
  const initialCount = await cards.count()
  expect(initialCount).toBeGreaterThanOrEqual(4)
  await expect(page.getByText(`Showing ${initialCount} of ${initialCount} results`)).toBeVisible()
  const inViewport = await cards.evaluateAll(elements => elements.filter(element => {
    const box = element.getBoundingClientRect()
    return box.top < window.innerHeight && box.bottom > 0
  }).length)
  expect(inViewport).toBeGreaterThanOrEqual(3)
  const resultsBox = await page.locator('.results-view').boundingBox()
  const firstCardBox = await cards.first().boundingBox()
  expect(resultsBox?.width).toBeGreaterThanOrEqual(1019)
  expect(resultsBox?.width).toBeLessThanOrEqual(1021)
  expect(firstCardBox?.height).toBeLessThanOrEqual(210)
  await expect(page.getByLabel(/Career gap of approximately/).first()).toBeVisible()
  await expect(page.locator('.candidate-rank')).toHaveCount(0)
  await expect(page.getByText('Why this match')).toHaveCount(0)

  await page.getByRole('button', { name: 'Refine' }).click()
  await expect(page.locator('.results-filter-panel')).toBeVisible()
  const refinedCardBox = await cards.first().boundingBox()
  const filterBox = await page.locator('.results-filter-panel').boundingBox()
  expect(filterBox?.x).toBeGreaterThan((refinedCardBox?.x || 0) + (refinedCardBox?.width || 0))
  await page.getByRole('button', { name: 'Projects' }).click()
  await expect(page.locator('.results-filter-panel')).toHaveCount(0)
  await expect(page.locator('.workspace-sidepanel')).toBeVisible()
  await page.getByRole('button', { name: 'Projects' }).click()
  await expect(page.locator('.workspace-sidepanel')).toHaveCount(0)
  await page.getByRole('button', { name: 'Refine' }).click()
  await page.getByLabel('Min. experience').fill('7')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect.poll(() => cards.count()).toBeLessThan(initialCount)
  await page.getByLabel('Min. experience').fill('')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect(cards).toHaveCount(initialCount)
  await page.getByLabel('Skills').fill('Python,Django')
  await page.getByLabel('Min. experience').fill('5')
  await page.getByLabel('Work preference').selectOption('Hybrid')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect.poll(() => cards.count()).toBeLessThan(initialCount)
  await expect(cards.first().getByText('Python', { exact: true })).toBeVisible()
  await page.getByLabel('Skills').fill('')
  await page.getByLabel('Min. experience').fill('')
  await page.getByLabel('Work preference').selectOption('')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect(cards).toHaveCount(initialCount)
  await page.getByLabel('Max. compensation').fill('1')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  await expect(page.getByRole('heading', { name: 'No candidates match these filters' })).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await expect(cards).toHaveCount(initialCount)

  const anikaName = candidates[0].name
  const anikaCard = cards.filter({ has: page.locator(`a[href="mailto:${candidates[0].email}"]`) })
  await expect(anikaCard.getByRole('heading', { name: anikaName, exact: true })).toBeVisible()
  await anikaCard.getByRole('checkbox').check()
  await cards.filter({ hasNotText: anikaName }).first().getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Compare', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Candidate comparison' })).toBeVisible()
  await expect(page.getByText('Career history')).toBeVisible()
  await expect(page.getByText('Work preferences')).toBeVisible()
  await expect(page.getByText('Meaningful work')).toBeVisible()
  await page.locator('.compare-modal .close').click()

  await anikaCard.getByRole('button', { name: 'View profile' }).click()
  const profileDrawer = page.locator('.profile-drawer')
  await expect(page.getByText('CANDIDATE PROFILE · SUBMITTED · VIEWED')).toBeVisible()
  await expect(profileDrawer.getByRole('link', { name: 'Resume' })).toBeVisible()
  await expect(profileDrawer.getByRole('link', { name: 'LinkedIn' })).toBeVisible()
  await expect(profileDrawer.getByRole('link', { name: 'GitHub' })).toBeVisible()
  await expect(profileDrawer.getByRole('link', { name: 'Email', exact: true })).toBeVisible()
  await expect(profileDrawer.getByRole('link', { name: 'WhatsApp', exact: true })).toBeVisible()
  await expect(page.getByText(`Built a resilient event platform at SignalWorks.`)).toBeVisible()
  await page.locator('.profile-drawer .close').click()
  await expect(anikaCard.locator('.name-row .signal.viewed')).toBeVisible()

  await anikaCard.getByRole('button', { name: /Save to Backend hiring/ }).click()
  await expect(page.getByText(/Candidate saved to Backend hiring/)).toBeVisible()
  await page.getByRole('button', { name: 'Projects' }).click()
  await page.locator('.workspace-sidepanel').getByRole('button', { name: new RegExp(`Backend hiring ${runId}`) }).click()
  await expect(page.getByRole('heading', { name: `Backend hiring ${runId}` })).toBeVisible()
  await expect(page.locator('.project-candidates').getByText(anikaName)).toBeVisible()
  await page.locator('.project-searches').getByRole('button').first().click()
  await expect(page.getByText(`Showing ${initialCount} of ${initialCount} results`)).toBeVisible()

  const stage = anikaCard.getByLabel(`Stage for ${anikaName}`)
  await stage.selectOption('sourced')
  await expect(stage).toHaveValue('sourced')
  await stage.selectOption('non_relevant')
  await expect(stage).toHaveValue('non_relevant')

  const fixture = fs.readFileSync(path.resolve('../backend/tests/fixtures/asha-rao-resume.docx'))
  const update = await request.post(`${API}/candidate/resumes/`, {
    headers: { Authorization: `Token ${candidates[0].token}` },
    multipart: { file: { name: 'asha-rao-updated.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: fixture } },
  })
  expect(update.ok()).toBeTruthy()
  const restoreName = await request.patch(`${API}/candidate/profile/`, {
    headers: { Authorization: `Token ${candidates[0].token}` },
    data: { full_name: anikaName, email: candidates[0].email },
  })
  expect(restoreName.ok()).toBeTruthy()
  await page.reload()
  await page.getByRole('button', { name: 'Candidate updates' }).click()
  await expect(page.getByText('Updated resume').first()).toBeVisible()
  await page.getByRole('button', { name: 'Recent searches' }).click()
  await page.locator('.workspace-sidepanel .workspace-list').getByRole('button').first().click()
  await expect(page.getByText(`Showing ${initialCount} of ${initialCount} results`)).toBeVisible()
  const persisted = page.locator('.candidate-card').filter({ has: page.locator(`a[href="mailto:${candidates[0].email}"]`) })
  await expect(persisted.getByLabel(`Stage for ${anikaName}`)).toHaveValue('non_relevant')
  await expect(persisted.locator('.name-row .signal.viewed')).toBeVisible()
  await expect(persisted.locator('.name-row .signal.updated')).toHaveText('Profile updated')
})
