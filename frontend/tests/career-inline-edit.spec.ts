import { expect, test } from '@playwright/test'

test.use({ hasTouch: true })

for (const width of [390, 768, 1440]) test(`candidate edits one missing date inline at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let endDate: string | null = null
  const edits: Array<{ path: string; body: Record<string, unknown> }> = []
  const resume = { id: 3, original_name: 'fictional.pdf', version: 1, uploaded_at: '2026-10-26T10:00:00Z', processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false, url: '/api/v1/resumes/3/download/' }
  const profile = () => ({ id: 9001, full_name: 'Fictional Candidate', email: 'fictional@example.test', headline: 'Engineer', total_experience: '6', skills: ['Python'], education: [], work_preferences: [],
    work_experiences: [
      { id: 8, company: 'Earlier Fictional Employer', role: 'Engineering Intern', start_date: '2013-06-01', end_date: '2013-08-01', date_label: 'Jun 2013 — Aug 2013', employment_type: 'Internship', confidence_status: 'supported', description: '', gap_reason: '' },
      { id: 7, company: 'Fictional Studio', role: 'Software Engineer', start_date: '2020-03-01', end_date: endDate, date_label: endDate ? 'Mar 2020 — Sep 2022' : 'Mar 2020 — End not specified', employment_type: 'Full-time', confidence_status: endDate ? 'candidate_confirmed' : 'supported', description: '', gap_reason: '' },
    ],
    career_preferences: {}, employment_extraction: { resume_id: 3, verified_role_ids: [7, 8], status: 'verified_fallback', source: 'rules', profile_state: 'applied', accepted_role_count: 2, saved_role_count: 2, stale_profile_preserved: false },
    meaningful_work: '', submission_missing_fields: [], can_submit: false, profile_status: 'draft', visibility: '', latest_resume: resume })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, role: 'candidate', full_name: 'Fictional Candidate', email: 'fictional@example.test' } })
    if (path.endsWith('/auth/csrf/')) return route.fulfill({ json: { csrfToken: 'fictional' } })
    if (path.endsWith('/candidate/profile/')) {
      if (route.request().method() !== 'GET') edits.push({ path, body: route.request().postDataJSON() })
      return route.fulfill({ json: profile() })
    }
    if (path.endsWith('/candidate/work-experiences/7/')) {
      const body = route.request().postDataJSON() as Record<string, unknown>
      edits.push({ path, body })
      endDate = '2022-09-01'
      return route.fulfill({ json: profile() })
    }
    return route.fulfill({ json: {} })
  })
  await page.route('**/*.mp4', route => route.abort())
  await page.goto('/')
  const card = page.locator('.cp-career-surface')
  const timeline = card.getByRole('list', { name: 'Career journey' })
  await expect(page.getByRole('button', { name: 'Edit profile' })).toBeVisible()
  await expect(timeline.locator('.career-sequence')).toHaveCount(2)
  await expect(card.getByText('1 role needs a date check')).toBeVisible()
  await card.getByRole('button', { name: 'Fix dates' }).click()
  const editor = card.getByRole('form', { name: /Edit Software Engineer/ })
  await expect(editor.getByRole('textbox', { name: 'Employer' })).toHaveValue('Fictional Studio')
  await expect(editor.getByRole('textbox', { name: 'Job title' })).toHaveValue('Software Engineer')
  await expect(editor.getByLabel('Start date')).toHaveValue('2020-03')
  await editor.getByLabel('End date').fill('2022-09')
  await card.screenshot({ path: `test-results/career-inline-edit-${width}.png`, animations: 'disabled' })
  await editor.getByRole('button', { name: 'Save' }).click()
  await expect(card.getByText('Career Journey updated. Your changes are saved.')).toBeVisible()
  expect(edits).toEqual([{ path: '/api/v1/candidate/work-experiences/7/', body: { end: { year: 2022, month: 9 } } }])
  await timeline.getByRole('button', { name: /Software Engineer at Fictional Studio/ }).focus()
  await expect(page.getByRole('tooltip')).toContainText('Mar 2020 — Sep 2022')
  await page.keyboard.press('Escape')
  expect(await timeline.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})

test('a mobile cluster opens direct editing without hiding any of 20 roles', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.route('**/career-edit-cluster-preview', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: `
    <html><head><meta charset="utf-8"><style>body{margin:0;background:#eaf0ee}*{box-sizing:border-box}</style></head><body><div id="review"></div><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
    RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    const {default:Timeline}=await import('/src/components/CandidateCareerTimeline.tsx');
    const roles=Array.from({length:20},(_,i)=>({id:i+1,company:'Fictional Employer '+String(i+1).padStart(2,'0'),role:i===0?'Engineering Intern':'Engineer '+(i+1),start_date:String(1980+i*2)+'-03-01',end_date:String(1981+i*2)+'-08-01',date_label:'Mar '+(1980+i*2)+' — Aug '+(1981+i*2),employment_type:i===0?'Internship':'Full-time',confidence_status:'supported',description:'',gap_reason:''}));
    const extraction={resume_id:1,status:'verified_ai',source:'ai',accepted_role_count:20,saved_role_count:20,verified_role_ids:roles.map(role=>role.id),unverified_role_ids:[],profile_state:'applied',stale_profile_preserved:false};
    ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{className:'candidate-experience',style:{padding:16}},React.createElement('section',{className:'cp-career-surface'},React.createElement(Timeline,{items:roles,extraction,saveRole:async()=>true}))));
    </script></body></html>` }))
  await page.goto('/career-edit-cluster-preview')
  const graph = page.getByRole('list', { name: 'Career journey' })
  await expect(graph.locator('.career-sequence')).toHaveCount(20)
  await graph.locator('.career-job.is-cluster').first().tap()
  const list = page.getByRole('dialog', { name: /roles grouped here/ })
  await expect(list).toContainText('Fictional Employer 01')
  await list.getByRole('button', { name: 'Edit this role' }).first().click()
  await expect(page.getByRole('form', { name: /Edit Engineering Intern/ })).toBeVisible()
  await expect(graph.locator('.career-sequence')).toHaveCount(20)
  expect(await graph.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true)
  await page.screenshot({ path: 'test-results/career-inline-cluster-390.png', animations: 'disabled', fullPage: true })
})

for (const width of [390, 768, 1440]) test(`clean Career Journey editing preview at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 })
  await page.route('**/career-edit-visual-preview', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: `
    <html><head><meta charset="utf-8"><style>body{margin:0;background:#eaf0ee}*{box-sizing:border-box}</style></head><body><div id="review"></div><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
    RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    const {default:Timeline}=await import('/src/components/CandidateCareerTimeline.tsx');
    const roles=[
      {id:8,company:'Fictional Research and Systems Studio International',role:'Engineering Intern',start_date:'2017-06-01',end_date:'2017-08-01',date_label:'Jun 2017 — Aug 2017',employment_type:'Internship',confidence_status:'supported',description:'',gap_reason:''},
      {id:7,company:'Fictional Studio',role:'Software Engineer',start_date:'2020-03-01',end_date:null,date_label:'Mar 2020 — End not specified',employment_type:'Full-time',confidence_status:'supported',description:'',gap_reason:''}
    ];
    const extraction={resume_id:1,status:'verified_ai',source:'ai',accepted_role_count:2,saved_role_count:2,verified_role_ids:[7,8],unverified_role_ids:[],profile_state:'applied',stale_profile_preserved:false};
    ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{className:'candidate-experience',style:{padding:${width < 500 ? 16 : 24},maxWidth:${width < 500 ? 390 : 1000}}},React.createElement('section',{className:'cp-career-surface'},React.createElement(Timeline,{items:roles,extraction,saveRole:async()=>true}))));
    </script></body></html>` }))
  await page.goto('/career-edit-visual-preview')
  await expect(page.getByText('1 role needs a date check')).toBeVisible()
  const marker = page.getByRole('button', { name: /Engineering Intern at Fictional Research and Systems Studio International/ })
  await page.locator('.career-history').screenshot({ path: `test-results/career-normal-${width}.png`, animations: 'disabled' })
  await marker.tap()
  const detail = page.getByRole('tooltip')
  await expect(detail).toContainText('Fictional Research and Systems Studio International')
  await expect(detail).toContainText('Engineering Intern')
  await expect(detail).toContainText('Jun 2017 — Aug 2017')
  await expect(detail).toContainText('Internship')
  const bounds = await detail.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
  await page.screenshot({ path: `test-results/career-detail-${width}.png`, animations: 'disabled', fullPage: true })
  await page.keyboard.press('Escape')
  await marker.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Edit this role' })).toBeFocused()
  await page.keyboard.press('Escape')
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  await page.screenshot({ path: `test-results/career-edit-prompt-${width}.png`, animations: 'disabled', fullPage: true })
  await page.getByRole('button', { name: 'Fix dates' }).click()
  await expect(page.getByRole('button', { name: 'Save' })).toBeVisible()
  await page.getByLabel('End date').fill('2022-09')
  await page.mouse.move(0, 0)
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await page.screenshot({ path: `test-results/career-edit-form-${width}.png`, animations: 'disabled', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})
