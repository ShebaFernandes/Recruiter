import { expect, test } from '@playwright/test'

test.use({ hasTouch:true })
for (const width of [390, 1440]) test(`single role, partial dates and extraction outcomes at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height:1000 })
  await page.emulateMedia({ reducedMotion:'reduce' })
  await page.route('**/history-states-review', route => route.fulfill({ contentType:'text/html; charset=utf-8', body:`
    <html><head><meta charset="utf-8"></head><body><div id="review"></div><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    import '/src/styles.css';
    import '/src/components/candidate-experience.css';
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type;
    window.__vite_plugin_react_preamble_installed__=true;
    const {default:Journey}=await import('/src/components/CareerJourney.tsx');
    const role={id:1,company:'Northstar Applied Research and Technology Cooperative',role:'Senior Platform Engineer',start_date:'2023-01-01',end_date:'2023-02-01',description:'Candidate-confirmed details.',confidence_status:'candidate_confirmed',gap_reason:''};
    const outcome=(status,extra={})=>({resume_id:2,verified_role_ids:[],status,source:'rules',accepted_role_count:0,saved_role_count:0,profile_state:'applied',stale_profile_preserved:false,...extra});
    const cases=[
      ['Single role',[role],outcome('verified_ai',{verified_role_ids:[1],accepted_role_count:1,source:'ai'})],
      ['Partial dates',[{...role,start_date:null,end_date:null,date_label:'2019 — 21'}],null],
      ['Declared no employment',[],outcome('confirmed_no_employment')],
      ['Extraction needs review',[],outcome('review_required')],
      ['Preserved manual history',[role],outcome('review_required',{stale_profile_preserved:true})],
    ];
    ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{style:{padding:20,maxWidth:900,margin:'auto'}},cases.map(([name,items,extraction])=>React.createElement('section',{'aria-label':name,key:name},React.createElement('h2',null,name),React.createElement(Journey,{items,extraction,detailed:true,presentAtEnd:true})))));
    </script></body></html>` }))
  await page.goto('/history-states-review')
  const single = page.getByRole('region', { name:'Single role' })
  const graph = single.getByRole('list', { name:'Career journey' })
  await expect(graph).toBeVisible()
  const line = await single.locator('.career-period-line').boundingBox()
  const bounds = await graph.boundingBox()
  expect(line!.width).toBeGreaterThan(200)
  expect(line!.width).toBeLessThanOrEqual(bounds!.width)
  expect(await graph.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
  await expect(single.locator('.career-role-summary')).toContainText('Northstar')
  await single.getByRole('button').tap()
  await expect(page.getByRole('tooltip')).toContainText('Candidate-confirmed details.')
  await page.keyboard.press('Escape')
  const partial = page.getByRole('region', { name:'Partial dates' })
  await expect(partial.locator('.career-period small')).toHaveText('2019')
  await partial.getByRole('button').tap()
  await expect(page.getByRole('tooltip')).toContainText('2019 — 21')
  await page.keyboard.press('Escape')
  await expect(partial).not.toContainText('Jan')
  expect(await partial.getByRole('list').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
  await expect(page.getByRole('region', { name:'Declared no employment' }).getByRole('status')).toContainText('declared in this resume')
  await expect(page.getByRole('region', { name:'Extraction needs review' }).getByRole('status')).toContainText('could not find supported employment history')
  const preserved = page.getByRole('region', { name:'Preserved manual history' })
  await expect(preserved.getByRole('status')).toHaveCount(0)
  await expect(preserved.locator('.career-journey')).toHaveCount(1)
  await expect(preserved.locator('.career-sequence.needs-review')).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path:info.outputPath(`employment-states-${width}.png`), fullPage:true })
})
