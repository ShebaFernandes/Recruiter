import { MarqueeDuplicate } from './marquee-context'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import './marquee.css'

type MarqueeProps = Omit<ComponentPropsWithoutRef<'div'>, 'children'> & {
  children: ReactNode
  pauseOnHover?: boolean
  speed?: 'slow' | 'normal' | 'fast'
}

export function Marquee({
  children,
  className = '',
  pauseOnHover = false,
  speed = 'normal',
  ...props
}: MarqueeProps) {
  return <div
    {...props}
    className={`ui-marquee ui-marquee--${speed}${pauseOnHover ? ' ui-marquee--pause' : ''} ${className}`.trim()}
    tabIndex={0}
  >
    <div className="ui-marquee__track">
      <div className="ui-marquee__group">{children}</div>
      <div className="ui-marquee__group" aria-hidden="true"><MarqueeDuplicate.Provider value={true}>{children}</MarqueeDuplicate.Provider></div>
    </div>
  </div>
}
