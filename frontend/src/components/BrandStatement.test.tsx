import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BrandStatement from './BrandStatement'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('BrandStatement', () => {
  it('renders the exact statement with only the product phrase emphasized', () => {
    render(<BrandStatement />)
    const heading = screen.getByRole('heading', { name: 'The right person changes the product, the pace and the possibility of what comes next.' })
    expect(heading).toBeVisible()
    expect(heading.querySelectorAll('em')).toHaveLength(1)
    expect(heading.querySelector('em')).toHaveTextContent('the product,')
  })

  it('reveals once when it enters the viewport', () => {
    let notify: IntersectionObserverCallback = () => undefined
    const disconnect = vi.fn()
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) { notify = callback }
      observe() {}
      disconnect = disconnect
    })
    render(<BrandStatement />)
    const section = screen.getByRole('heading').closest('section')
    expect(section).toHaveClass('is-reveal-ready')
    act(() => notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver))
    expect(section).toHaveClass('is-visible')
    expect(disconnect).toHaveBeenCalled()
  })

  it('stays immediately visible when reduced motion is requested', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
    render(<BrandStatement />)
    expect(screen.getByRole('heading').closest('section')).not.toHaveClass('is-reveal-ready')
  })
})
