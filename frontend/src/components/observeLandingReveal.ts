/** One-shot reveal: preserve each section's CSS sequence, start on entry rather than a page-load timer. */
export default function observeLandingReveal(
  target: HTMLElement,
  threshold: number,
  owner = target,
  visibleClass = 'is-visible',
) {
  const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  let observer: IntersectionObserver | undefined
  const reveal = () => {
    owner.classList.add(visibleClass)
    observer?.disconnect()
  }
  const motionChanged = () => { if (preference?.matches) reveal() }
  try {
    if (preference?.matches || typeof IntersectionObserver !== 'function') {
      reveal()
      return () => {}
    }
    observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) reveal()
    }, { threshold: Math.min(threshold, window.innerHeight * .2 / Math.max(target.offsetHeight, 1)) })
    observer.observe(target)
    owner.classList.add('is-reveal-ready')
    preference?.addEventListener?.('change', motionChanged)
  } catch {
    reveal()
  }
  return () => {
    observer?.disconnect()
    preference?.removeEventListener?.('change', motionChanged)
    owner.classList.remove('is-reveal-ready')
  }
}
