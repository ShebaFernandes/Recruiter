# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cinematic-landing.spec.ts >> restored landing 390
- Location: tests/cinematic-landing.spec.ts:3:42

# Error details

```
Error: locator.evaluateAll: EncodingError: The source image cannot be decoded.
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - main [ref=e5]:
    - link "Skip to content" [ref=e6] [cursor=pointer]:
      - /url: "#enter-home"
    - generic [ref=e7]:
      - generic [ref=e8]:
        - link "Enter home" [ref=e9] [cursor=pointer]:
          - /url: "#enter-home"
          - img "enter" [ref=e10]
        - navigation "Main navigation" [ref=e11]:
          - button "For recruiters" [ref=e12] [cursor=pointer]
          - button "For candidates" [ref=e13] [cursor=pointer]
          - group [ref=e14]:
            - generic "Log in" [ref=e15] [cursor=pointer]
      - region [ref=e16]:
        - generic [ref=e17]:
          - heading "The best teams are built by ENTER." [level=1] [ref=e18]:
            - text: The best teams arebuilt by
            - generic [aria-hidden] [ref=e19]: .
          - generic [ref=e22]:
            - paragraph [ref=e23]: What You Build Tomorrow Depends on Who You Hire Today
            - paragraph [ref=e24]: Every breakthrough product, high-performing team, and successful company is built by exceptional people. We help ambitious companies hire them.
    - region "Company logos" [ref=e25]:
      - button "Pause company logos" [ref=e26] [cursor=pointer]
      - generic [ref=e28]:
        - generic [ref=e29]:
          - button "About Shiprocket" [ref=e30] [cursor=pointer]
          - button "About WazirX" [ref=e31] [cursor=pointer]
          - button "About CRED" [ref=e32] [cursor=pointer]
          - button "About Nanonets" [ref=e33] [cursor=pointer]:
            - generic [ref=e34]: Nanonets
          - button "About CoinDCX" [ref=e36] [cursor=pointer]
          - button "About Navi" [ref=e37] [cursor=pointer]
          - button "About MPL" [ref=e38] [cursor=pointer]
          - button "About Dream11" [ref=e39] [cursor=pointer]
          - button "About TrueFoundry" [ref=e40] [cursor=pointer]
          - button "About Kindred Group" [ref=e41] [cursor=pointer]
          - button "About Practo" [ref=e42] [cursor=pointer]
          - button "About Arintra" [ref=e43] [cursor=pointer]
          - button "About Orange Health" [ref=e44] [cursor=pointer]
          - button "About Zepto" [ref=e45] [cursor=pointer]
          - button "About CoinSwitch" [ref=e46] [cursor=pointer]
          - button "About PagarBook" [ref=e47] [cursor=pointer]
          - button "About HackerEarth" [ref=e48] [cursor=pointer]
          - button "About JustAnswer" [ref=e49] [cursor=pointer]
          - button "About Mindtickle" [ref=e50] [cursor=pointer]
          - button "About CommerceIQ" [ref=e51] [cursor=pointer]
          - button "About SatSure" [ref=e52] [cursor=pointer]
          - button "About SpiceJet" [ref=e53] [cursor=pointer]
          - button "About Signeasy" [ref=e54] [cursor=pointer]
          - button "About Locus" [ref=e55] [cursor=pointer]
          - button "About SpotOn" [ref=e56] [cursor=pointer]
          - button "About Parspec" [ref=e57] [cursor=pointer]
          - button "About SentiSum" [ref=e58] [cursor=pointer]
        - generic [aria-hidden] [ref=e59]:
          - generic [aria-hidden] [ref=e60] [cursor=pointer]
          - generic [aria-hidden] [ref=e61] [cursor=pointer]
          - generic [aria-hidden] [ref=e62] [cursor=pointer]
          - generic [ref=e64] [cursor=pointer]: Nanonets
          - generic [aria-hidden] [ref=e66] [cursor=pointer]
          - generic [aria-hidden] [ref=e67] [cursor=pointer]
          - generic [aria-hidden] [ref=e68] [cursor=pointer]
          - generic [aria-hidden] [ref=e69] [cursor=pointer]
          - generic [aria-hidden] [ref=e70] [cursor=pointer]
          - generic [aria-hidden] [ref=e71] [cursor=pointer]
          - generic [aria-hidden] [ref=e72] [cursor=pointer]
          - generic [aria-hidden] [ref=e73] [cursor=pointer]
          - generic [aria-hidden] [ref=e74] [cursor=pointer]
          - generic [aria-hidden] [ref=e75] [cursor=pointer]
          - generic [aria-hidden] [ref=e76] [cursor=pointer]
          - generic [aria-hidden] [ref=e77] [cursor=pointer]
          - generic [aria-hidden] [ref=e78] [cursor=pointer]
          - generic [aria-hidden] [ref=e79] [cursor=pointer]
          - generic [aria-hidden] [ref=e80] [cursor=pointer]
          - generic [aria-hidden] [ref=e81] [cursor=pointer]
          - generic [aria-hidden] [ref=e82] [cursor=pointer]
          - generic [aria-hidden] [ref=e83] [cursor=pointer]
          - generic [aria-hidden] [ref=e84] [cursor=pointer]
          - generic [aria-hidden] [ref=e85] [cursor=pointer]
          - generic [aria-hidden] [ref=e86] [cursor=pointer]
          - generic [aria-hidden] [ref=e87] [cursor=pointer]
          - generic [aria-hidden] [ref=e88] [cursor=pointer]
  - button "Pause background animation" [ref=e89] [cursor=pointer]
```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test'
  2  | 
  3  | for (const width of [390,768,1024,1440]) test(`restored landing ${width}`, async ({page}, info) => {
  4  |   await page.setViewportSize({width,height:1000})
  5  |   await page.route('**/api/v1/**',route=>route.fulfill({status:401,json:{}}))
  6  |   await page.goto('/')
  7  |   await expect(page.locator('.simple-landing')).toBeVisible()
  8  |   await expect(page.locator('.ce-company-preview')).toHaveCSS('background-color','rgba(0, 0, 0, 0)')
  9  |   await page.evaluate(()=>document.fonts.ready)
> 10 |   await page.locator('.landing-background img').evaluateAll(async images=>Promise.all(images.map(img=>(img as HTMLImageElement).decode())))
     |                                                 ^ Error: locator.evaluateAll: EncodingError: The source image cannot be decoded.
  11 |   await expect(page.locator('.landing-background img')).toHaveCount(1)
  12 |   await expect(page.locator('video,.ce-product-preview,.ce-hero-actions')).toHaveCount(0)
  13 |   await expect(page.locator('.ce-intro h1')).toHaveCSS('animation-name','none')
  14 |   const scene=page.locator('.landing-background__scene')
  15 |   await expect(scene).toHaveCSS('animation-duration','28s')
  16 |   await expect(page.locator('.landing-background img')).toHaveAttribute('src','/hero/golden-alpine-valley.png')
  17 |   await expect(page.locator('.ce-nanonets-lockup').first()).toHaveText('Nanonets')
  18 |   await page.getByRole('button',{name:'Pause background animation'}).click()
  19 |   await expect(scene).toHaveCSS('animation-play-state','paused')
  20 |   expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  21 |   await page.screenshot({path:info.outputPath(`restored-${width}.png`),fullPage:true})
  22 |   await page.getByText('Log in',{exact:true}).click()
  23 |   await expect(page.getByRole('button',{name:'Candidate log in'})).toBeVisible()
  24 |   await page.getByRole('button',{name:'Candidate log in'}).click()
  25 |   await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible()
  26 |   await page.goto('/')
  27 |   await page.getByTestId('for-candidates').click()
  28 |   await expect(page.getByRole('heading',{name:'Create your account'})).toBeVisible()
  29 |   await page.goto('/')
  30 |   await page.getByTestId('for-recruiters').click()
  31 |   await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible()
  32 |   await page.goto('/')
  33 |   await page.emulateMedia({reducedMotion:'reduce'})
  34 |   await expect(scene).toHaveCSS('animation-name','none')
  35 |   await expect(page.locator('.landing-motion-toggle')).toBeHidden()
  36 | })
  37 | 
```