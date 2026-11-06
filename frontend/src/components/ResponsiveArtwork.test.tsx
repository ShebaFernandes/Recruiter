import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import ResponsiveArtwork from './ResponsiveArtwork'

const artwork = { width: 1200, height: 600, original: '/original.png', preview: 'data:image/webp;base64,preview', webp: '/large.webp', webpSrcSet: '/small.webp 640w, /large.webp 1200w', avif: '/large.avif', avifSrcSet: '/small.avif 640w, /large.avif 1200w' }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

it('keeps real image sources deferred until the image itself is nearby', () => {
  let notify: IntersectionObserverCallback = () => {}
  const disconnect = vi.fn()
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { notify = callback }
    observe = vi.fn()
    disconnect = disconnect
  })
  const view = render(<ResponsiveArtwork artwork={artwork} alt="Landscape" sizes="100vw" />)
  const image = view.getByAltText('Landscape')
  expect(image).toHaveAttribute('src', artwork.preview)
  expect(view.container.querySelector('source')).toBeNull()
  act(() => notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver))
  expect(image).toHaveAttribute('srcset', artwork.webpSrcSet)
  expect(view.container.querySelector('source')).toHaveAttribute('srcset', artwork.avifSrcSet)
  expect(disconnect).toHaveBeenCalled()
})

it('falls back from AVIF through WebP and the original to a persistent preview', () => {
  const view = render(<ResponsiveArtwork artwork={artwork} eager alt="Landscape" />)
  const image = view.getByAltText('Landscape')
  fireEvent.error(image)
  expect(view.container.querySelector('source')).toBeNull()
  expect(image).toHaveAttribute('src', artwork.webp)
  fireEvent.error(image)
  expect(image).toHaveAttribute('src', artwork.original)
  expect(image).not.toHaveAttribute('srcset')
  fireEvent.error(image)
  expect(image).toHaveAttribute('src', artwork.preview)
})

it('retains dimensions and loads above-the-fold artwork eagerly without raising its priority', () => {
  const view = render(<ResponsiveArtwork artwork={artwork} eager alt="Landscape" />)
  const image = view.getByAltText('Landscape')
  expect(image).toHaveAttribute('width', '1200')
  expect(image).toHaveAttribute('height', '600')
  expect(image).toHaveAttribute('loading', 'eager')
  expect(image).toHaveAttribute('fetchpriority', 'low')
})

it('loads safely when observation is unavailable or its constructor fails', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('IntersectionObserver', class { constructor() { throw new Error('Unavailable') } })
  const view = render(<ResponsiveArtwork artwork={artwork} alt="Landscape" />)
  await act(() => vi.runAllTimersAsync())
  expect(view.getByAltText('Landscape')).toHaveAttribute('src', artwork.webp)
})
