import { createPortal } from 'react-dom'
import { MarqueeDuplicate } from './marquee-context'
import { useContext, useEffect, useRef, useState } from 'react'
import { Quote } from 'lucide-react'
import { CardContent, LiquidCard } from './liquid-glass-card'
import './marquee-card.css'

type MarqueeCardProps = {
  name: string
  role: string
  paragraphs: string[]
}

export function MarqueeCard({ name, role, paragraphs }: MarqueeCardProps) {
  const duplicate = useContext(MarqueeDuplicate)
  const [highlighted, setHighlighted] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!highlighted) return
    const previousFocus = document.activeElement as HTMLElement | null
    dialogRef.current?.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow; previousFocus?.focus({ preventScroll: true }) }
  }, [highlighted])
  const initials = name.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase()

  return <><LiquidCard className={`testimonial-glass-card${highlighted ? ' is-highlighted' : ''}`} tabIndex={duplicate ? undefined : 0} onClick={() => setHighlighted(value => !value)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setHighlighted(value => !value) } }} role="article" aria-label={`${name} testimonial`}>
    <CardContent className="testimonial-glass-card__content">
      <div className="testimonial-glass-card__person">
        <span className="testimonial-glass-card__avatar" aria-hidden="true">{initials}</span>
        <div className="testimonial-glass-card__identity">
          <strong>{name}</strong>
          <span>{role}</span>
        </div>
        <Quote className="testimonial-glass-card__quote" size={15} aria-hidden="true" />
      </div>
      <blockquote>{paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</blockquote>
    </CardContent>
  </LiquidCard>{highlighted && createPortal(<dialog ref={dialogRef} className="testimonial-reader" aria-label={`${name} testimonial`} onCancel={() => setHighlighted(false)} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) setHighlighted(false) } }}>
    <button type="button" className="testimonial-reader__close" aria-label="Close testimonial" onClick={() => setHighlighted(false)}>×</button>
    <h2>{name}</h2><p className="testimonial-reader__role">{role}</p>
    <blockquote>{paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</blockquote>
  </dialog>, document.body)}</>
}
