import type { ComponentProps } from 'react'
import './liquid-glass-card.css'

export function LiquidCard({ className = '', ...props }: ComponentProps<'div'>) {
  return <div data-slot="card" className={`liquid-card ${className}`.trim()} {...props} />
}

export function CardContent({ className = '', ...props }: ComponentProps<'div'>) {
  return <div data-slot="card-content" className={`liquid-card__content ${className}`.trim()} {...props} />
}
