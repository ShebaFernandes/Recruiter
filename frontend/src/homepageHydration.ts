/** Schedule noncritical work after the existing intro; input always takes priority. */
export function afterHomepageIntro(root: HTMLElement): Promise<void> {
  const animations = root.querySelector('#ce-title')?.getAnimations?.()
    .filter(animation => animation.playState !== 'finished' && animation.playState !== 'idle') ?? []
  if (!animations.length) return Promise.resolve()
  return new Promise(resolve => {
    let finished = false
    let frame = 0
    const finish = () => {
      if (finished) return
      finished = true
      window.clearTimeout(timeout)
      window.cancelAnimationFrame(frame)
      for (const event of ['pointerdown', 'keydown', 'wheel', 'touchstart']) root.removeEventListener(event, finish, true)
      resolve()
    }
    const timeout = window.setTimeout(finish, 1500)
    for (const event of ['pointerdown', 'keydown', 'wheel', 'touchstart']) root.addEventListener(event, finish, { capture: true, passive: true })
    void Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      // Animation completion resolves before paint; leave that final frame free of startup work.
      if (!finished) frame = window.requestAnimationFrame(() => {
        if (!finished) frame = window.requestAnimationFrame(finish)
      })
    })
  })
}
