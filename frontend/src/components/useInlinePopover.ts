import { useLayoutEffect, type RefObject } from 'react'

/** Keep inline menus attached to their trigger without clipping at viewport edges. */
export default function useInlinePopover(
  open: boolean,
  setOpen: (open: boolean) => void,
  trigger: RefObject<HTMLButtonElement | null>,
  popup: RefObject<HTMLElement | null>,
) {
  useLayoutEffect(() => {
    if (!open || !trigger.current || !popup.current) return
    const anchor = trigger.current
    const panel = popup.current
    const position = () => {
      const viewport = window.visualViewport
      const left = viewport?.offsetLeft ?? 0
      const top = viewport?.offsetTop ?? 0
      const width = viewport?.width ?? window.innerWidth
      const height = viewport?.height ?? window.innerHeight
      const rect = anchor.getBoundingClientRect()
      panel.style.setProperty('max-height', `${Math.min(panel.classList.contains('wb-listbox__menu') ? 280 : 440, height - 24)}px`)
      const bounds = panel.getBoundingClientRect()
      const below = rect.bottom + 10
      const desiredTop = below + bounds.height <= top + height - 12 ? below : rect.top - bounds.height - 10
      panel.style.setProperty('left', `${Math.max(left + 12, Math.min(rect.left + rect.width / 2 - bounds.width / 2, left + width - bounds.width - 12))}px`)
      panel.style.setProperty('top', `${Math.max(top + 12, Math.min(desiredTop, top + height - bounds.height - 12))}px`)
    }
    const outside = (event: PointerEvent) => {
      if (!anchor.closest('.wb-inline-field')?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setOpen(false)
      anchor.focus({ preventScroll: true })
    }
    position()
    window.addEventListener('resize', position)
    window.addEventListener('scroll', position, true)
    window.visualViewport?.addEventListener('resize', position)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      window.removeEventListener('resize', position)
      window.removeEventListener('scroll', position, true)
      window.visualViewport?.removeEventListener('resize', position)
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  })
}
