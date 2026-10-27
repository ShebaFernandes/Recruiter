import { expect, test } from '@playwright/test'
test.use({ hasTouch:true, actionTimeout:10000 })
for (const width of [390, 1440]) test(`marker-only shared timeline interactions at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height:900 })
  await page.emulateMedia({ reducedMotion:'reduce' })
  await page.route('**/timeline-review', route => route.fulfill({ contentType:'text/html; charset=utf-8', body:`
    <html><head><meta charset="utf-8"></head><body><div id="review"></div><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
    RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    const {default:Journey}=await import('/src/components/CareerJourney.tsx');
    const items=[
    {id:1,company:'Northstar Applied Research Cooperative',role:'Software Engineering Intern',start_date:'2018-03-01',end_date:'2018-08-01',employment_type:'Internship',confidence_status:'supported',description:'Built research tools.',gap_reason:''},
    {id:2,company:'Northstar Applied Research Cooperative',role:'Software Engineer',start_date:'2018-09-01',end_date:'2020-12-01',employment_type:'Full-time',confidence_status:'supported',description:'Built the platform.',gap_reason:''},
    {id:3,company:'Maple Systems',role:'Engineering Lead',start_date:'2022-01-01',end_date:'2024-12-01',employment_type:'Full-time',confidence_status:'candidate_confirmed',description:'Led the engineering team.',gap_reason:'Study break'}];
    const extraction={resume_id:4,status:'verified_fallback',source:'rules',accepted_role_count:2,saved_role_count:3,verified_role_ids:[1,2],unverified_role_ids:[3],candidate_confirmed_role_ids:[3],stale_profile_preserved:true,profile_state:'not_applied'};
    ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{style:{padding:'48px 20px',maxWidth:1280,margin:'auto'}},
      React.createElement('h1',null,'Career Journey'),
      ...['Candidate','Recruiter'].map(name=>React.createElement('section',{'aria-label':name,key:name,style:{marginTop:32,padding:24,background:'rgba(255,255,255,.92)',borderRadius:16}},React.createElement('h2',null,name),React.createElement(Journey,{items,extraction,detailed:name==='Recruiter'})))));
    </script></body></html>` }))
  await page.goto('/timeline-review')
  const candidate = page.getByRole('region', { name:'Candidate' })
  const graph = candidate.getByRole('list', { name:'Career journey' })
  await expect(graph.locator('.career-period')).toHaveCount(3)
  await expect(graph.locator('.career-role-summary')).toHaveCount(0)
  await expect(graph).not.toContainText('Northstar')
  await expect(graph).not.toContainText('Software')
  await expect(graph).not.toContainText('Mar')
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  expect((await graph.innerText()).replace(/\s/g,'')).toMatch(/^\d+$/)
  await expect(graph.locator('.career-period small')).toHaveText(['2018','2018','2022'])
  await expect(graph.locator('.career-sequence.needs-review')).toHaveCount(1)
  await expect(graph.locator('.career-gap-period')).toHaveCount(1)
  await expect(graph.locator('.career-gap-line')).toHaveCSS('border-top-style','dashed')
  await expect(graph.locator('.is-internship .career-period-line')).toHaveCSS('background-color','rgb(143, 199, 196)')
  const targets = await graph.locator('.career-period .career-job').all()
  for (const target of targets) { const box = await target.boundingBox(); expect(box!.width).toBeGreaterThanOrEqual(44); expect(box!.height).toBeGreaterThanOrEqual(44) }
  if (width === 390) expect(await graph.evaluate(el=>el.scrollWidth>el.clientWidth)).toBe(true)
  const lines = await graph.locator('.career-sequence>.career-period-line').evaluateAll(els=>els.map(el=>el.getBoundingClientRect().y))
  expect(new Set(lines).size).toBe(1)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({ path:info.outputPath(`default-${width}.png`), fullPage:true })
  const intern = graph.getByRole('button', { name:/Software Engineering Intern at/ })
  if (width === 1440) await intern.hover(); else await intern.tap()
  const popover = page.getByRole('tooltip')
  await expect(popover).toContainText('Northstar Applied Research Cooperative')
  await expect(popover).toContainText('Software Engineering Intern')
  await expect(popover).toContainText('Mar 2018 — Aug 2018')
  await expect(popover).toContainText('Internship')
  const card = await popover.boundingBox()
  expect(card!.x).toBeGreaterThanOrEqual(0); expect(card!.x+card!.width).toBeLessThanOrEqual(width)
  await page.screenshot({ path:info.outputPath(`details-${width}.png`), fullPage:false })
  await expect(popover).toBeVisible()
  await page.mouse.move(0,0)
  await page.keyboard.press('Escape')
  await expect(popover).toHaveCount(0)
  for (const region of ['Candidate','Recruiter']) {
    const marker = page.getByRole('region', { name:region }).getByRole('button', { name:/Engineering Lead at Maple/ })
    await marker.focus()
    await expect(popover).toContainText('Full-time')
    await expect(popover).toContainText('Review needed')
    await expect(popover).toContainText('Candidate-confirmed or manually edited')
    await page.keyboard.press('Escape')
    await marker.tap()
    await expect(popover).toContainText('Engineering Lead')
    await marker.tap()
    await expect(popover).toHaveCount(0)
  }
  await graph.getByRole('button', { name:/Career gap/ }).focus()
  await expect(popover).toContainText('Study break')
  await page.keyboard.press('Escape')
})
