import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EnterLogo from './EnterLogo'

describe('EnterLogo', () => {
  it('renders the official wordmark with an accessible name', () => {
    render(<EnterLogo alt="ENTER Recruitment" />)

    const logo = screen.getByRole('img', { name: 'ENTER Recruitment' })
    expect(logo.getAttribute('viewBox')).toBe('145 145 1110 310')
    expect(logo.querySelector('image')?.getAttribute('href')).toBe('/enter-wordmark.svg')
  })

  it('can be decorative when its parent supplies the accessible name', () => {
    const { container } = render(<EnterLogo decorative />)

    expect(container.querySelector('[role="img"]')).toBeNull()
    expect(container.querySelector('.enter-logo-mark')?.getAttribute('aria-hidden')).toBe('true')
  })
})
