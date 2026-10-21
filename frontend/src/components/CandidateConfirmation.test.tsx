import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import CandidateConfirmation from './CandidateConfirmation'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('shows the approved confirmation and informational explanations without settings or forms', () => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  const { container } = render(<CandidateConfirmation onViewProfile={() => {}} />)
  expect(screen.getByRole('heading', { name: "You're in." })).toHaveFocus()
  expect(screen.getByText('PROFILE SUBMITTED')).toBeVisible()
  expect(screen.getByText('Your profile has been submitted successfully. When a relevant opportunity comes along, ENTER can help connect you with the right people.')).toBeVisible()
  expect(screen.getAllByRole('listitem')).toHaveLength(3)
  expect(screen.getByText('When your profile matches their search and your availability settings permit discovery.')).toBeVisible()
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  expect(container.querySelector('form,input,select')).toBeNull()
  expect(screen.getAllByRole('button')).toHaveLength(1)
  expect([...container.querySelectorAll('svg')].every(icon => icon.getAttribute('aria-hidden') === 'true')).toBe(true)
})

it('uses only the supplied navigation callback, never a form submission', () => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  const view = vi.fn()
  render(<CandidateConfirmation onViewProfile={view} />)
  const button = screen.getByRole('button', { name: 'View my profile' })
  expect(button).toHaveAttribute('type', 'button')
  fireEvent.click(button)
  expect(view).toHaveBeenCalledTimes(1)
})
