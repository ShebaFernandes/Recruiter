import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import PlatformBackground from './PlatformBackground'
vi.mock('./platform-poster.jpg?inline', () => ({ default: '/matching-poster.jpg' }))

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  Object.defineProperty(HTMLVideoElement.prototype, 'requestVideoFrameCallback', { configurable: true, value: vi.fn() })
  Object.defineProperty(HTMLVideoElement.prototype, 'cancelVideoFrameCallback', { configurable: true, value: vi.fn() })
})
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals()
  Reflect.deleteProperty(HTMLVideoElement.prototype, 'requestVideoFrameCallback')
  Reflect.deleteProperty(HTMLVideoElement.prototype, 'cancelVideoFrameCallback')
})

it('renders a matching poster and interactive content before media loads', () => {
  const view = render(<PlatformBackground><input aria-label="Email" /></PlatformBackground>)
  const background = view.container.querySelector('.platform-background')!
  const video = view.container.querySelector('video')!
  expect(background.getAttribute('style')).toContain('background-image')
  expect(video.poster).toBeTruthy()
  expect(background).toHaveAttribute('data-media-ready', 'false')
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'synthetic@example.test' } })
  expect(screen.getByLabelText('Email')).toHaveValue('synthetic@example.test')
  fireEvent.error(video)
  expect(view.container.querySelector('video')).toBeNull()
  expect(background.getAttribute('style')).toContain('background-image')
})

it('reveals the first presented frame without a playback-time threshold', () => {
  let present: VideoFrameRequestCallback | undefined
  vi.spyOn(HTMLVideoElement.prototype, 'requestVideoFrameCallback').mockImplementation(callback => { present = callback; return 1 })
  vi.spyOn(HTMLVideoElement.prototype, 'cancelVideoFrameCallback').mockImplementation(() => {})
  const view = render(<PlatformBackground>Login</PlatformBackground>)
  const video = view.container.querySelector('video')!
  Object.defineProperty(video, 'readyState', { value: 2 })
  fireEvent.loadedData(video)
  expect(view.container.querySelector('.platform-background')).toHaveAttribute('data-media-ready', 'false')
  act(() => present?.(0, {} as VideoFrameCallbackMetadata))
  expect(view.container.querySelector('.platform-background')).toHaveAttribute('data-media-ready', 'true')
  expect(video.currentTime).toBe(0)
})

it('keeps the same video when platform content changes', () => {
  const view = render(<PlatformBackground>Signup</PlatformBackground>)
  const video = view.container.querySelector('video')!
  view.rerender(<PlatformBackground>Login</PlatformBackground>)
  expect(view.container.querySelector('video')).toBe(video)
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1)
})

it('uses a still without fetching video for reduced motion', () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
  const view = render(<PlatformBackground>Login</PlatformBackground>)
  expect(view.container.querySelector('video')).toBeNull()
  expect(view.container.querySelector('.platform-background')?.getAttribute('style')).toContain('background-image')
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it('supports decoded-frame readiness when video frame callbacks are unavailable', () => {
  Reflect.deleteProperty(HTMLVideoElement.prototype, 'requestVideoFrameCallback')
  const view = render(<PlatformBackground>Login</PlatformBackground>)
  const video = view.container.querySelector('video')!
  fireEvent.loadedData(video)
  expect(view.container.querySelector('.platform-background')).toHaveAttribute('data-media-ready', 'false')
  Object.defineProperty(video, 'readyState', { value: 2 })
  fireEvent.loadedData(video)
  expect(view.container.querySelector('.platform-background')).toHaveAttribute('data-media-ready', 'true')
})

it('retains the poster when autoplay is rejected', async () => {
  vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValue(new DOMException('Not allowed', 'NotAllowedError'))
  const view = render(<PlatformBackground>Login</PlatformBackground>)
  await act(async () => {})
  expect(view.container.querySelector('video')).toBeNull()
  expect(view.container.querySelector('.platform-background')).toHaveAttribute('data-render-state', 'fallback')
  expect(view.container.querySelector('.platform-background')?.getAttribute('style')).toContain('background-image')
})

it('pauses hidden-page playback and resumes without remounting the video', () => {
  const view = render(<PlatformBackground>Login</PlatformBackground>)
  const video = view.container.querySelector('video')!
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  expect(video.pause).toHaveBeenCalled()
  hidden.mockReturnValue(false)
  fireEvent(document, new Event('visibilitychange'))
  expect(video.play).toHaveBeenCalledTimes(2)
  expect(view.container.querySelector('video')).toBe(video)
})
