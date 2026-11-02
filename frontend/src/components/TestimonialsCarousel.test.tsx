import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TestimonialsCarousel from './TestimonialsCarousel'

afterEach(cleanup)

describe('TestimonialsCarousel', () => {
  it('opens the full testimonial and closes it without losing the page', () => {
    const original = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: vi.fn(function (this: HTMLDialogElement) { this.setAttribute('open', '') }) })
    render(<TestimonialsCarousel />)
    fireEvent.click(screen.getByRole('article', { name: 'Githin Joseph testimonial' }))
    const dialog = screen.getByRole('dialog', { name: 'Githin Joseph testimonial' })
    expect(dialog.textContent).toContain('They have a good understanding of the talent market.')
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close testimonial' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.body.style.overflow).not.toBe('hidden')
    if (original) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', original)
    else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
  })

  it('shows the complete text of every client testimonial without read-more controls', () => {
    render(<TestimonialsCarousel />)

    expect(screen.getByRole('heading', {
      name: 'Don’t take our word for it',
    })).toBeTruthy()

    const originalGroup = document.querySelector('.ui-marquee__group:not([aria-hidden])') as HTMLElement
    const cards = within(originalGroup).getAllByRole('article')
    expect(cards).toHaveLength(5)

    expect(cards.map(card => card.querySelector('.testimonial-glass-card__identity strong')?.textContent)).toEqual([
      'Githin Joseph', 'Steve Francis', 'Drushya Shetty', 'Divya V', 'Prachi Sharma',
    ])
    expect(cards[1].textContent).toContain("I've worked with enter Recruitment")
    expect(cards[1].textContent).toContain("I'd recommend")
    expect(cards[2].textContent).toContain('a dependable recruitment partner!')
    expect(cards[3].textContent).toContain('future hiring requirements.')
    expect(cards[4].textContent).toContain('Looking forward to our continued partnership.')

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('duplicates the row for seamless motion without repeating it for assistive technology', () => {
    render(<TestimonialsCarousel />)

    const groups = document.querySelectorAll('.ui-marquee__group')
    expect(groups).toHaveLength(2)
    expect(groups[1].getAttribute('aria-hidden')).toBe('true')
    expect(groups[1].querySelectorAll('.testimonial-glass-card')).toHaveLength(5)
    expect(groups[1].querySelector('[tabindex]')).toBeNull()
  })
})
