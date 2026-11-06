import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { afterHomepageIntro } from './homepageHydration'

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => window.setTimeout(() => callback(0), 16))
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(id => window.clearTimeout(id))
})
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })
function intro() {
  const root = document.createElement('div')
  root.innerHTML = '<h1 id="ce-title">Headline</h1>'
  let finish = () => {}
  const finished = new Promise<void>(resolve => { finish = resolve })
  const animation = { playState: 'running', finished, cancel: vi.fn() }
  Object.defineProperty(root.firstElementChild, 'getAnimations', { value: () => [animation] })
  return { root, animation, finish }
}
it('waits for the existing intro and its final paint without cancelling it', async () => {
  const { root, animation, finish } = intro()
  let hydrated = false
  const ready = afterHomepageIntro(root).then(() => { hydrated = true })
  await vi.advanceTimersByTimeAsync(100)
  expect(hydrated).toBe(false)
  finish()
  await vi.advanceTimersByTimeAsync(16)
  expect(hydrated).toBe(false)
  await vi.advanceTimersByTimeAsync(32)
  await ready
  expect(hydrated).toBe(true)
  expect(animation.cancel).not.toHaveBeenCalled()
})
it.each(['pointerdown', 'keydown'])('gives %s priority over the intro wait', async event => {
  const { root, animation } = intro()
  const ready = afterHomepageIntro(root)
  root.dispatchEvent(new Event(event, { bubbles: true }))
  await ready
  expect(animation.cancel).not.toHaveBeenCalled()
})
it('has a bounded fallback if the browser never reports animation completion', async () => {
  const { root } = intro()
  const ready = afterHomepageIntro(root)
  await vi.advanceTimersByTimeAsync(1500)
  await ready
})
