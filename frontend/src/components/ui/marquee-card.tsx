import { Quote } from 'lucide-react'
import { CardContent, LiquidCard } from './liquid-glass-card'
import './marquee-card.css'

type MarqueeCardProps = {
  name: string
  role: string
  paragraphs: string[]
}

export function MarqueeCard({ name, role, paragraphs }: MarqueeCardProps) {
  const initials = name.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase()

  return <LiquidCard className="testimonial-glass-card" role="article" aria-label={`${name} testimonial`}>
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
  </LiquidCard>
}
