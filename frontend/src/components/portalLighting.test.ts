import { afterEach, expect, it, vi } from 'vitest'
import { portalLighting } from './portalLighting'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('caps pixel density and releases the observer and canvas backing store', () => {
  const disconnect = vi.fn()
  vi.stubGlobal('ResizeObserver', class { observe = vi.fn(); disconnect = disconnect })
  vi.stubGlobal('devicePixelRatio', 3)
  const setTransform = vi.fn()
  const canvas = document.createElement('canvas')
  vi.spyOn(canvas, 'getContext').mockReturnValue({ setTransform } as unknown as CanvasRenderingContext2D)
  const scene = document.createElement('section')
  Object.defineProperties(scene, { clientWidth: { value:390 }, clientHeight: { value:900 } })
  const light = portalLighting(canvas, scene, document.createElement('div'))!
  expect(canvas.width).toBe(585)
  expect(canvas.height).toBe(1350)
  expect(setTransform).toHaveBeenCalledWith(1.5, 0, 0, 1.5, 0, 0)
  light.dispose()
  expect(disconnect).toHaveBeenCalledOnce()
  expect(canvas.width).toBe(0)
  expect(canvas.height).toBe(0)
})
it('allows CSS fallback when canvas is unavailable', () => {
  const canvas = document.createElement('canvas')
  vi.spyOn(canvas, 'getContext').mockReturnValue(null)
  expect(portalLighting(canvas, document.createElement('section'), document.createElement('div'))).toBeNull()
})
