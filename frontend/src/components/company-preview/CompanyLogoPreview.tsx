import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { previewCompanies } from './companies'
import './company-logo-preview.css'

type Company = typeof previewCompanies[number]
type Detail = { company: Company; anchor: HTMLElement; left: number; top: number; above: boolean; pinned: boolean }

/** Public landing marquee; the owner approved public display on 2026-10-12. */
export default function CompanyLogoMarquee() {
  const root = useRef<HTMLElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const focusFrame = useRef<number>(0)
  const tooltipId = useId()
  const [detail, setDetail] = useState<Detail | null>(null)
  const [paused, setPaused] = useState(false)
  const [inView, setInView] = useState(true)
  const [pageHidden, setPageHidden] = useState(false)
  const [keyboardMode, setKeyboardMode] = useState(false)
  // Fill wide screens while artwork is pending without duplicating tab stops.
  const sequenceCompanies = Array.from({ length: Math.ceil(10 / previewCompanies.length) }, () => previewCompanies).flat()

  function cancelLeave() { clearTimeout(leaveTimer.current) }
  function show(company: Company, anchor: HTMLElement, pinned = false) {
    cancelLeave()
    const rect = anchor.getBoundingClientRect()
    const width = Math.min(288, window.innerWidth - 32)
    const above = window.innerHeight - rect.bottom < 160
    setDetail({ company, anchor, pinned, above,
      left: Math.max(16, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 16)),
      top: above ? rect.top - 8 : rect.bottom + 8 })
  }
  function leave() {
    cancelLeave()
    // Allow the pointer to cross the small gap to the hoverable information popup.
    leaveTimer.current = setTimeout(() => setDetail(current =>
      current?.pinned || current?.anchor === document.activeElement ? current : null), 140)
  }

  useEffect(() => {
    const element = root.current
    let observer: IntersectionObserver | null = null
    try {
      if (typeof IntersectionObserver === 'function') {
        observer = new IntersectionObserver(entries => setInView(entries[0].isIntersecting))
        if (element) observer.observe(element)
      }
    } catch {
      // An optional offscreen optimization must never break the public page.
      observer?.disconnect()
      observer = null
    }
    const visibility = () => setPageHidden(document.hidden)
    document.addEventListener('visibilitychange', visibility)
    return () => {
      observer?.disconnect()
      document.removeEventListener('visibilitychange', visibility)
      clearTimeout(leaveTimer.current)
      cancelAnimationFrame(focusFrame.current)
    }
  }, [])

  useEffect(() => {
    if (!detail) return
    const dismiss = () => setDetail(null)
    const outside = (event: PointerEvent) => {
      const target = event.target as Node
      if (!detail.anchor.contains(target) && !popup.current?.contains(target)) dismiss()
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') dismiss() }
    // Fixed-position portal cannot be clipped by the marquee. Dismiss when its
    // anchor moves rather than running a permanent positioning animation loop.
    window.addEventListener('resize', dismiss)
    window.addEventListener('scroll', dismiss, true)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      window.removeEventListener('resize', dismiss)
      window.removeEventListener('scroll', dismiss, true)
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [detail])

  return <section ref={root} className="ce-company-preview" aria-label="Company logos"
    style={{ '--company-loop-scale': sequenceCompanies.length / 10 } as CSSProperties}
    data-paused={paused || !!detail || !inView || pageHidden} data-keyboard={keyboardMode}
    onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) {
        setKeyboardMode(false)
        setDetail(null)
      }
    }}>
    {/* No visual toolbar: preserve a keyboard/screen-reader motion control
        without reserving a row between the scenery and company artwork. */}
    <button type="button" className="ce-company-pause" aria-pressed={paused}
      onClick={() => setPaused(value => !value)}>
      {paused ? 'Resume company logos' : 'Pause company logos'}
    </button>
    <div className="ce-company-window" onPointerLeave={leave}>
      <div className="ce-company-track">
        {[false, true].map(duplicate => <div key={String(duplicate)} className="ce-company-sequence"
          aria-hidden={duplicate || undefined} data-duplicate={duplicate}>
          {sequenceCompanies.map((company, index) => {
            const repeated = index >= previewCompanies.length
            const image = <img src={company.logo} alt="" draggable={false} data-treatment={company.treatment}
              style={{ maxHeight: company.height }} />
            // The visual copy supports pointer/touch but never duplicates keyboard
            // or screen-reader stops. Keyboard mode exposes the original full row.
            return duplicate || repeated ? <span key={`${company.id}-${index}`} className="ce-company-logo"
              aria-hidden="true" data-repeated={repeated || undefined}
              onPointerEnter={event => { if (event.pointerType === 'mouse') show(company, event.currentTarget) }}
              onPointerLeave={leave}
              onClick={event => {
                if (detail?.anchor === event.currentTarget && detail.pinned) setDetail(null)
                else show(company, event.currentTarget, true)
              }}>{image}</span>
              : <button key={company.id} type="button" className="ce-company-logo"
                aria-label={`About ${company.name}`}
                aria-describedby={detail?.company.id === company.id ? tooltipId : undefined}
                onPointerEnter={event => { if (event.pointerType === 'mouse') show(company, event.currentTarget) }}
                onPointerLeave={leave}
                onFocus={event => {
                  if (!event.currentTarget.matches(':focus-visible')) return
                  const anchor = event.currentTarget
                  setKeyboardMode(true)
                  cancelAnimationFrame(focusFrame.current)
                  focusFrame.current = requestAnimationFrame(() => {
                    anchor.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' })
                    // Let the row's scroll event settle before opening details;
                    // otherwise scrolling to later logos immediately dismisses them.
                    focusFrame.current = requestAnimationFrame(() => {
                      if (document.activeElement === anchor) show(company, anchor)
                    })
                  })
                }}
                onClick={event => {
                  if (detail?.anchor === event.currentTarget && detail.pinned) setDetail(null)
                  else show(company, event.currentTarget, true)
                }}>{image}</button>
          })}
        </div>)}
      </div>
    </div>
    {detail && createPortal(<div ref={popup} id={tooltipId} role="tooltip" className="ce-company-popover"
      style={{ left: detail.left, top: detail.top, transform: detail.above ? 'translateY(-100%)' : undefined }}
      onPointerEnter={cancelLeave} onPointerLeave={leave}>
      <strong>{detail.company.name}</strong>
      <span>{detail.company.category}</span>
      <p>{detail.company.description}</p>
    </div>, document.body)}
  </section>
}
