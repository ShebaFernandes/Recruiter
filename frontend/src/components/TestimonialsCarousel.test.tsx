import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import TestimonialsCarousel from './TestimonialsCarousel'

afterEach(cleanup)

describe('TestimonialsCarousel', () => {
  it('shows the complete text of every client testimonial without read-more controls', () => {
    render(<TestimonialsCarousel />)

    expect(screen.getByRole('heading', {
      name: 'Don’t take our word for it, here’s what our clients have to say.',
    })).toBeTruthy()

    const originalGroup = document.querySelector('.ui-marquee__group:not([aria-hidden])') as HTMLElement
    const cards = within(originalGroup).getAllByRole('article')
    expect(cards).toHaveLength(4)

    expect(cards.map(card => card.querySelector('.testimonial-glass-card__identity strong')?.textContent)).toEqual([
      'Steve Francis', 'Drushya Shetty', 'Divya V', 'Prachi Sharma',
    ])
    expect(cards[0].textContent).toContain("I've worked with enter Recruitment")
    expect(cards[0].textContent).toContain("I'd recommend")
    expect(cards[1].textContent).toContain('a dependable recruitment partner!')
    expect(cards[2].textContent).toContain('future hiring requirements.')
    expect(cards[3].textContent).toContain('Looking forward to our continued partnership.')

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('duplicates the row for seamless motion without repeating it for assistive technology', () => {
    render(<TestimonialsCarousel />)

    const groups = document.querySelectorAll('.ui-marquee__group')
    expect(groups).toHaveLength(2)
    expect(groups[1].getAttribute('aria-hidden')).toBe('true')
    expect(groups[1].querySelectorAll('.testimonial-glass-card')).toHaveLength(4)
    expect(groups[1].querySelector('[tabindex]')).toBeNull()
  })
})
