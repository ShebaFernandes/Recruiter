import { expect, test } from '@playwright/test'
test.use({ hasTouch: true })

for (const width of [390, 768, 1440]) for (const count of [1, 2, 5, 10, 20]) {
  test(`fitted timeline keeps ${count} roles accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.route('**/timeline-fit-review*', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: `
      <html><head><meta charset="utf-8"><style>body{margin:0;background:#eaf0ee}*{box-sizing:border-box}</style></head><body><div id="review"></div><script type="module">
      import React from '/node_modules/.vite/deps/react.js';
      import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      import RefreshRuntime from '/@react-refresh';
      import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
      RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
      const {default:Journey}=await import('/src/components/CareerJourney.tsx');
      const count=new URLSearchParams(location.search).get('count')*1;
      const roles=Array.from({length:count},(_,i)=>({id:i+1,company:'Fictional Employer '+String(i+1).padStart(2,'0'),role:i===0?'Engineering Intern':'Engineer '+(i+1),start_date:String(1980+i*2)+'-03-01',end_date:String(1981+i*2)+'-08-01',date_label:'Mar '+(1980+i*2)+' — Aug '+(1981+i*2),employment_type:i===0?'Internship':'Full-time',confidence_status:'supported',description:'Fictional role',gap_reason:''}));
      const extraction={resume_id:1,status:'verified_ai',source:'ai',accepted_role_count:count,saved_role_count:count,verified_role_ids:roles.map(role=>role.id),unverified_role_ids:[],profile_state:'applied',stale_profile_preserved:false};
      ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{style:{maxWidth:1120,margin:'24px auto',padding:'0 16px'}},React.createElement('section',{'aria-label':'Candidate career card',style:{padding:20,background:'#fff',borderRadius:18}},React.createElement('h1',{style:{fontSize:20}},'Your career journey'),React.createElement(Journey,{items:roles,extraction}))));
      </script></body></html>` }))
    await page.goto(`/timeline-fit-review?count=${count}`)
    const card = page.getByRole('region', { name: 'Candidate career card' })
    const graph = card.getByRole('list', { name: 'Career journey' })
    await expect(graph.locator('.career-sequence')).toHaveCount(count)
    await expect(graph.locator('.career-role-summary')).toHaveCount(0)
    await expect(graph.locator('.career-sequence.is-internship')).toHaveCount(1)
    await expect(graph.locator('.career-sequence.is-verified')).toHaveCount(count)
    expect(await graph.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    const bounds = await graph.boundingBox()
    const markers = graph.locator('.career-period .career-job')
    const markerCount = await markers.count()
    expect(markerCount).toBeGreaterThan(0)
    expect(markerCount).toBeLessThanOrEqual(count)
    const boxes = await markers.evaluateAll(elements => elements.map(element => {
      const box = element.getBoundingClientRect()
      return { x:box.x, y:box.y, width:box.width, height:box.height }
    }))
    const seenEmployers = new Set<string>()
    for (let i = 0; i < markerCount; i++) {
      const marker = markers.nth(i)
      const box = boxes[i]
      expect(box.width).toBeGreaterThanOrEqual(44)
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.x).toBeGreaterThanOrEqual(bounds!.x - 1)
      expect(box.x + box.width).toBeLessThanOrEqual(bounds!.x + bounds!.width + 1)
      await marker.focus()
      const clustered = (await marker.getAttribute('aria-haspopup')) === 'dialog'
      const popover = clustered ? page.getByRole('dialog') : page.getByRole('tooltip')
      await expect(popover).toBeVisible()
      const contents = await popover.innerText()
      for (let role = 1; role <= count; role++) {
        const employer = `Fictional Employer ${String(role).padStart(2, '0')}`
        const dates = `Mar ${1980 + (role - 1) * 2} — Aug ${1981 + (role - 1) * 2}`
        if (contents.includes(employer) && contents.includes(dates)) seenEmployers.add(employer)
      }
      const popoverBox = (await popover.boundingBox())!
      expect(popoverBox.x).toBeGreaterThanOrEqual(0)
      expect(popoverBox.x + popoverBox.width).toBeLessThanOrEqual(width)
      expect(popoverBox.y).toBeGreaterThanOrEqual(0)
      expect(popoverBox.y + popoverBox.height).toBeLessThanOrEqual(900)
      await page.keyboard.press('Escape')
    }
    expect(seenEmployers.size).toBe(count)
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      expect(Math.abs(boxes[i].y - boxes[j].y)).toBeLessThan(1)
      expect(boxes[i].x + boxes[i].width <= boxes[j].x + 1 || boxes[j].x + boxes[j].width <= boxes[i].x + 1).toBe(true)
    }
    if (count > 1) await expect(graph.locator('.career-gap-line').first()).toHaveCSS('border-top-style', 'dashed')
    if ((width === 1440 && count === 5) || (width === 390 && [5, 20].includes(count))) {
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
      await card.screenshot({ path: `test-results/final-timeline-${width}-${count}.png`, animations: 'disabled' })
      const clustered = (await markers.first().getAttribute('aria-haspopup')) === 'dialog'
      await markers.first().tap()
      await expect(clustered ? page.getByRole('dialog') : page.getByRole('tooltip')).toContainText('Engineering Intern')
      await page.screenshot({ path: `test-results/final-timeline-${width}-${count}-details.png`, fullPage: true, animations: 'disabled' })
      await page.keyboard.press('Escape')
      await expect(markers.first()).toBeFocused()
      await expect(page.getByRole('dialog')).toHaveCount(0)
    }
  })
}
