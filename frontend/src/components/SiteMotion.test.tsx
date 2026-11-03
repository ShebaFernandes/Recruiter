import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createElement } from 'react'
import SiteMotion from './SiteMotion'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); Reflect.deleteProperty(Element.prototype, 'animate') })
for (const mode of ['missing', 'throws']) it(`leaves content available when intersection observation ${mode}`, () => {
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  vi.stubGlobal('IntersectionObserver', mode === 'missing' ? undefined : class { constructor() { throw new Error('Unavailable observer') } })
  Object.defineProperty(Element.prototype, 'animate', { configurable: true, value: vi.fn() })
  render(createElement('main', null, createElement(SiteMotion), createElement('h1', null, 'Opportunity details')))
  expect(screen.getByRole('heading', { name: 'Opportunity details' })).toBeTruthy()
})
