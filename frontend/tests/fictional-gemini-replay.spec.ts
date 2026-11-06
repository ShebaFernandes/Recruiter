import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'

const fixtures = JSON.parse(readFileSync(path.resolve('../backend/tests/fixtures/fictional-gemini-employment.json'), 'utf8')) as {fixture:string; rows:Record<string, unknown>[]}[]
test.use({ hasTouch: true })
for (const width of [390, 1440]) for (const fixture of fixtures) {
  test(`${fixture.fixture}: saved extraction and manual edit at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.route('**/fictional-replay', route => route.fulfill({ contentType:'text/html; charset=utf-8', body:`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="root"></div><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
document.getElementById('root').dataset.items=JSON.stringify(${JSON.stringify(fixture.rows.map((r,i)=>({...r,id:i+1})))});
await import('/tests/fictional-replay-harness.tsx');
</script></body></html>` }))
    await page.goto('/fictional-replay')
    await expect(page.locator('.career-period')).toHaveCount(fixture.rows.length)
    for (const row of fixture.rows) await expect(page.getByRole('button', {name: new RegExp(`^${String(row.role).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')} at ${String(row.company).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}`)})).toBeAttached()
    const marker = page.locator('.career-period button').first()
    const originalPeriod = (await marker.getAttribute('aria-label'))!.split(', ')[1]
    await marker.click()
    await expect(page.getByRole('tooltip')).toBeVisible()
    await page.getByRole('button',{name:'Edit this role'}).click()
    const editor=page.getByRole('form')
    await editor.getByRole('textbox',{name:'Job title'}).fill('Fictional Edited Engineer')
    await editor.getByRole('button',{name:'Save',exact:true}).click()
    await expect(page.getByRole('button',{name:/Fictional Edited Engineer at/})).toBeAttached()
    await expect(page.getByRole('button',{name:/Fictional Edited Engineer at/})).toHaveAttribute('aria-label', new RegExp(originalPeriod.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')))
    await expect(page.getByRole('status')).toContainText('changes are saved')
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
    await page.screenshot({path:info.outputPath(`replay-${width}.png`)})
  })
}
