import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import CandidateUploadMedia from './CandidateUploadMedia'
import AnimatedGradient from './ui/animated-gradient'

const gl = {
  VERTEX_SHADER: 1, FRAGMENT_SHADER: 2, COMPILE_STATUS: 3, LINK_STATUS: 4, ARRAY_BUFFER: 5, STATIC_DRAW: 6, FLOAT: 7, TRIANGLES: 8,
  createShader: vi.fn(() => ({})), shaderSource: vi.fn(), compileShader: vi.fn(), getShaderParameter: vi.fn(() => true),
  createProgram: vi.fn(() => ({})), attachShader: vi.fn(), linkProgram: vi.fn(), getProgramParameter: vi.fn(() => true), useProgram: vi.fn(),
  createBuffer: vi.fn(() => ({})), bindBuffer: vi.fn(), bufferData: vi.fn(), getAttribLocation: vi.fn(() => 0), enableVertexAttribArray: vi.fn(), vertexAttribPointer: vi.fn(),
  getUniformLocation: vi.fn(() => ({})), uniform1f: vi.fn(), uniform2f: vi.fn(), uniform4f: vi.fn(), viewport: vi.fn(), drawArrays: vi.fn(),
  deleteProgram: vi.fn(), deleteShader: vi.fn(), deleteBuffer: vi.fn(),
}
let motion: { matches: boolean; addEventListener: ReturnType<typeof vi.fn>; removeEventListener: ReturnType<typeof vi.fn> }
let intersect: (entries: Array<{ isIntersecting: boolean }>) => void
let resized: () => void
const disconnect = vi.fn()
beforeEach(() => {
  vi.clearAllMocks(); vi.useFakeTimers()
  gl.getShaderParameter.mockReturnValue(true); gl.getProgramParameter.mockReturnValue(true)
  motion = { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }
  vi.stubGlobal('matchMedia', () => motion)
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16))
  vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id))
  vi.stubGlobal('ResizeObserver', class { constructor(cb: () => void) { resized = cb } observe() {} disconnect = disconnect })
  vi.stubGlobal('IntersectionObserver', class { constructor(cb: typeof intersect) { intersect = cb } observe() {} disconnect = disconnect })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(((kind: string) => kind === 'webgl2' ? gl : { fillStyle: '', fillRect() {}, getImageData: () => ({ data: [247, 249, 252, 255] }) }) as unknown as typeof HTMLCanvasElement.prototype.getContext)
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('renders at approximately 30 FPS, pauses, resumes, and has no media assets', () => {
  const { container } = render(<CandidateUploadMedia />)
  vi.advanceTimersByTime(1000)
  expect(gl.drawArrays.mock.calls.length).toBeGreaterThan(20)
  expect(gl.drawArrays.mock.calls.length).toBeLessThanOrEqual(32)
  expect(container.querySelector('video,img')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Pause background animation' }))
  const count = gl.drawArrays.mock.calls.length
  vi.advanceTimersByTime(1000)
  expect(gl.drawArrays).toHaveBeenCalledTimes(count)
  fireEvent.click(screen.getByRole('button', { name: 'Play background animation' }))
  vi.advanceTimersByTime(100)
  expect(gl.drawArrays.mock.calls.length).toBeGreaterThan(count)
})
it('uses only CSS with reduced motion or unavailable WebGL', () => {
  motion.matches = true
  const view = render(<CandidateUploadMedia />)
  expect(gl.createShader).not.toHaveBeenCalled()
  expect(view.container.querySelector('.upload-background')).toHaveAttribute('data-render-state', 'fallback')
  view.unmount()
  motion.matches = false
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  const other = render(<CandidateUploadMedia />)
  expect(other.container.querySelector('canvas')).toHaveAttribute('hidden')
  expect(other.container.querySelector('.upload-background')?.getAttribute('style')).toContain('linear-gradient')
})
it('pauses off-screen and when the document is hidden', () => {
  render(<CandidateUploadMedia />)
  intersect([{ isIntersecting: false }])
  const count = gl.drawArrays.mock.calls.length
  vi.advanceTimersByTime(1000)
  expect(gl.drawArrays).toHaveBeenCalledTimes(count)
  intersect([{ isIntersecting: true }])
  vi.advanceTimersByTime(100)
  expect(gl.drawArrays.mock.calls.length).toBeGreaterThan(count)
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  const hiddenCount = gl.drawArrays.mock.calls.length
  vi.advanceTimersByTime(1000)
  expect(gl.drawArrays).toHaveBeenCalledTimes(hiddenCount)
})
it('handles context loss/restoration, then releases resources and observers', () => {
  const view = render(<StrictMode><CandidateUploadMedia /></StrictMode>)
  const canvas = view.container.querySelector('canvas')!
  fireEvent(canvas, new Event('webglcontextlost', { cancelable: true }))
  expect(canvas).toHaveAttribute('hidden')
  fireEvent(canvas, new Event('webglcontextrestored'))
  expect(canvas).not.toHaveAttribute('hidden')
  view.unmount()
  expect(gl.deleteProgram.mock.calls.length).toBe(gl.createProgram.mock.calls.length)
  expect(gl.deleteShader.mock.calls.length).toBe(gl.createShader.mock.calls.length)
  expect(gl.deleteBuffer.mock.calls.length).toBe(gl.createBuffer.mock.calls.length)
  expect(disconnect).toHaveBeenCalledTimes(4)
  expect(vi.getTimerCount()).toBe(0)
})
it('does not reinitialize for equivalent configuration values', () => {
  const view = render(<AnimatedGradient config={{ preset: 'Prism', speed: 2 }} />)
  view.rerender(<AnimatedGradient config={{ preset: 'Prism', speed: 2 }} />)
  expect(gl.createProgram).toHaveBeenCalledTimes(1)
})
it('caps high-DPI rendering to 1.5 DPR and approximately 1.2 million pixels', () => {
  vi.stubGlobal('devicePixelRatio', 4)
  const { container } = render(<CandidateUploadMedia />)
  const background = container.querySelector('.upload-background')!
  Object.defineProperty(background, 'clientWidth', { value: 2400 })
  Object.defineProperty(background, 'clientHeight', { value: 1600 })
  resized()
  const canvas = container.querySelector('canvas')!
  expect(canvas.width / 2400).toBeLessThanOrEqual(1.5)
  expect(canvas.width * canvas.height).toBeLessThan(1_203_000)
})
it('releases partially allocated resources on shader or link failure', () => {
  gl.getShaderParameter.mockReturnValue(false)
  const first = render(<AnimatedGradient />)
  expect(gl.deleteShader).toHaveBeenCalledTimes(1)
  expect(gl.createProgram).not.toHaveBeenCalled()
  first.unmount()
  gl.getShaderParameter.mockReturnValue(true); gl.getProgramParameter.mockReturnValue(false)
  const second = render(<AnimatedGradient />)
  expect(second.container.querySelector('canvas')).toHaveAttribute('hidden')
  expect(gl.deleteProgram).toHaveBeenCalledTimes(1)
  expect(gl.deleteShader).toHaveBeenCalledTimes(3)
})
