import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Badge, Button, Card, Chip, FormField } from './ui'

afterEach(cleanup)

describe('design-system primitives', () => {
  it('composes button variants without losing native behavior', () => {
    render(<Button variant="secondary" fullWidth disabled>Continue</Button>)
    const button = screen.getByRole('button', { name: 'Continue' })
    expect(button).toBeDisabled()
    expect(button).toHaveClass('ui-button--secondary', 'ui-button--full')
  })

  it('keeps fields and hints accessibly associated', () => {
    render(<FormField label="Work email" name="email" hint="Use your company address." />)
    const field = screen.getByLabelText('Work email')
    expect(field).toHaveAttribute('aria-describedby', 'email-hint')
    expect(screen.getByText('Use your company address.')).toHaveAttribute('id', 'email-hint')
  })

  it('renders cards, badges, and interactive chips predictably', () => {
    render(<Card><Badge>New</Badge><Chip selected>Remote</Chip></Card>)
    expect(screen.getByText('New')).toHaveClass('ui-badge--violet')
    expect(screen.getByRole('button', { name: 'Remote' })).toHaveAttribute('aria-pressed', 'true')
  })
})
