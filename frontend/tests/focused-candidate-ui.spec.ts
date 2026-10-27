import { expect, test } from '@playwright/test'

// Exercise the production app with fictional API responses; no real accounts or AI calls.
for (const width of [390, 1440]) test(`non-interactive processing and calendar timeline at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let uploaded = false, done = false
  const motivators = ['Founder']
  let workerAvailable = true
  const patches: unknown[] = [], uploads: string[] = []
  const resume = { id:2, original_name:'Fictional-Engineer.pdf', version:2, uploaded_at:'2026-10-26T10:00:00Z', processing_status:'queued', scan_status:'quarantined', processing_error:'', can_retry:false, url:null }
  const completed = { ...resume, processing_status:'completed', scan_status:'clean' }
  const items = [
    { company:'Northstar Research', role:'Engineering Intern', start_date:'2020-01-01', end_date:'2020-07-01', employment_type:'Internship', description:'Built research tools.', gap_reason:'' },
    { company:'Northstar Research', role:'Software Engineer', start_date:'2020-07-01', end_date:'2022-07-01', description:'Built reliable services.', gap_reason:'' },
    { company:'Sample Systems', role:'Senior Engineer', start_date:'2023-01-01', end_date:'2024-01-01', description:'Led a platform team.', gap_reason:'Study break' },
    { company:'Sample Systems', role:'Staff Engineer', start_date:'2024-01-01', end_date:null, is_current:true, description:'Led platform architecture.', gap_reason:'' },
  ]
  const profile = () => ({ id:9001, full_name:'Fictional Test Candidate', email:'fictional@example.test', headline:'Staff Engineer', total_experience:'6', skills:['Python','Django'], education:[], work_preferences:[], work_experiences:done ? items.map((item,index)=>({...item,id:index+1})) : [], notice_period_days:null, career_preferences:{ motivators, preferred_locations:['Pune'] }, employment_extraction: done ? {resume_id:2,verified_role_ids:[1,2,3,4],status:'verified_ai', source:'ai', profile_state:'applied', accepted_role_count:4, saved_role_count:4, stale_profile_preserved:false} : null, meaningful_work:'', submission_missing_fields:[], can_submit:false, profile_status:'draft', visibility:'', latest_resume:uploaded ? done ? completed : resume : null })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json:{ id:9001, role:'candidate', full_name:'Fictional Test Candidate', email:'fictional@example.test' } })
    if (path.endsWith('/candidate/profile/')) {
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON(); patches.push(body)
      }
      return route.fulfill({ json:profile() })
    }
    if (path.endsWith('/candidate/resumes/')) {
      uploads.push(route.request().postData() || '')
      uploaded = true; done = false
      return route.fulfill({ status:202, json:profile() })
    }
    if (path.endsWith('/candidate/resume-status/')) return route.fulfill({ json:{ resume:done ? completed : resume, worker_available:workerAvailable } })
    return route.fulfill({ json:{} })
  })
  await page.route('**/*.mp4', route => route.abort())
  await page.goto('/')
  await expect(page.locator('link[rel="icon"][sizes="32x32"]')).toHaveAttribute('href','/favicon-32.png')
  const icon = await page.request.get('/favicon-32.png')
  expect(icon.status()).toBe(200)
  expect(icon.headers()['content-type']).toContain('image/png')
  const input = page.getByTestId('resume-input')
  for (const replacement of [false, true]) {
    await input.setInputFiles({ name:'fictional.pdf', mimeType:'application/pdf', buffer:Buffer.from('UI fixture only') })
    await expect(page.getByRole('heading', { name:'While we get to know you…' })).toBeVisible()
    const prompts = page.getByRole('region', { name:'Something to reflect on' })
    await expect(prompts.locator('li')).toHaveText(['Harder problems','More ownership','Exceptional people','Compensation'])
    await expect(prompts.locator('input,button,[tabindex]')).toHaveCount(0)
    await expect(page.locator('.processing-card input[type=checkbox]')).toHaveCount(0)
    await prompts.getByText('Harder problems', { exact:true }).click()
    expect(patches).toHaveLength(0)
    await expect(page.getByText("We're turning your experience into a clearer picture of your career.")).toBeVisible()
    expect(uploads.at(-1)).toContain('name="resume_ai_accepted"\r\n\r\nfalse')
    await expect(page.locator('.cp-processing-bar span')).toHaveCSS('animation-name','none')
    await expect(page.locator('.cp-processing-status')).toContainText('Queued')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path:info.outputPath(`${replacement ? 'update' : 'upload'}-${width}.png`), fullPage:true })
    if (replacement) {
      workerAvailable = false
      await expect(page.getByRole('button', { name:'Check status again' })).toBeVisible({ timeout:20000 })
      await expect(page.locator('.cp-loading-orbit')).toHaveCSS('animation-name','none')
      await expect(page.locator('.cp-processing-status')).toContainText('temporarily delayed')
      await page.screenshot({ path:info.outputPath(`delayed-${width}.png`), fullPage:true })
    }
    done = true
    await expect(page.getByRole('heading', { name:"Here's how we understand you." })).toBeVisible({ timeout:20000 })
  }
  const timeline = page.getByRole('list', { name:'Career journey' })
  await timeline.scrollIntoViewIfNeeded()
  await expect(timeline.locator('.career-period')).toHaveCount(4)
  await expect(page.locator('.career-history-status')).toContainText('verified against the latest resume’s evidence')
  await expect(timeline.locator('.is-internship')).toHaveCount(1)
  await expect(timeline.locator('.is-internship .career-period-line')).toHaveCSS('background-color','rgb(143, 199, 196)')
  await expect(timeline.locator('.career-gap-line')).toHaveCSS('border-top-style','dashed')
  const engineer = timeline.getByRole('button', { name:/Software Engineer at Northstar/ })
  await engineer.focus()
  await expect(page.getByRole('tooltip')).toContainText('Jul 2020 — Jul 2022')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  if (width === 390) expect(await timeline.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.locator('.cp-career-heading h3').click()
  await timeline.evaluate(el => { el.scrollLeft = 0 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path:info.outputPath(`career-${width}.png`), fullPage:true })
})
