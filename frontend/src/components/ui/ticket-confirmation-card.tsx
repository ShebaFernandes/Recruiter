import { forwardRef, useEffect, useState, type HTMLAttributes, type CSSProperties } from 'react'
import './ticket-confirmation-card.css'

/** Ticket presentation only: the caller owns confirmation data and navigation. */
export const AnimatedTicket = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function AnimatedTicket({ children, className = '', ...props }, ref) {
    const [celebrate, setCelebrate] = useState(false)
    useEffect(() => {
      const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
      if (!preference) return
      const update = () => setCelebrate(!preference.matches)
      update()
      preference.addEventListener('change', update)
      const timer = window.setTimeout(() => setCelebrate(false), 4500)
      return () => { clearTimeout(timer); preference.removeEventListener('change', update) }
    }, [])
    return <div ref={ref} className={`enter-ticket ${className}`} {...props}>
      {celebrate && <div className="enter-ticket-confetti" aria-hidden="true">
        {Array.from({ length: 32 }, (_, i) => <i key={i} style={{
          left: `${(i * 37) % 100}%`, '--delay': `${(i % 7) * .12}s`,
          '--drift': `${(i % 2 ? 1 : -1) * (20 + i % 45)}px`,
          '--turn': `${180 + i * 17}deg`,
        } as CSSProperties} />)}
      </div>}
      {children}
    </div>
  },
)
