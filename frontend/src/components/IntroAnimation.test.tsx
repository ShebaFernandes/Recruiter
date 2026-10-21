import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
beforeEach(() => {
  vi.resetModules()
  sessionStorage.clear()
  vi.useFakeTimers()
  vi.stubGlobal('scrollTo', vi.fn())
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches:false, addEventListener:vi.fn(), removeEventListener:vi.fn() })))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })
async function mount() {
  const { default: Intro } = await import('./IntroAnimation')
  return render(<Intro><section id="enter-home" tabIndex={-1}>Existing landing</section></Intro>)
}
it('opens automatically, releases focus and skips repeat visits', async () => {
  const view = await mount()
  expect(screen.getByRole('region', { name:'Welcome to ENTER' })).toHaveFocus()
  act(() => { vi.advanceTimersByTime(1400) })
  const shell = view.container.querySelector('.enter-intro-shell') as HTMLElement
  expect(parseFloat(shell.style.getPropertyValue('--intro-rotation'))).toBeGreaterThan(0)
  act(() => { vi.advanceTimersByTime(3100) })
  expect(screen.queryByRole('region')).not.toBeInTheDocument()
  expect(screen.getByText('Existing landing')).toHaveFocus()
  expect(screen.getByText('Existing landing').parentElement).not.toHaveAttribute('inert')
  view.unmount()
  await mount()
  expect(screen.queryByRole('button', { name:'Skip intro' })).not.toBeInTheDocument()
})
it('Skip cancels the intro immediately', async () => {
  await mount()
  fireEvent.click(screen.getByRole('button', { name:'Skip intro' }))
  expect(screen.queryByRole('region')).not.toBeInTheDocument()
})
it('bypasses motion for reduced-motion users', async () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches:true })))
  await mount()
  expect(screen.queryByRole('region')).not.toBeInTheDocument()
})
it('fails open when storage is unavailable', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked') })
  await mount()
  expect(screen.queryByRole('region')).not.toBeInTheDocument()
})
