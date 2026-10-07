import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
  localStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('Enter Talent landing', () => {
  it('offers connected recruiter and candidate entry points', () => {
    render(<App />)
    expect(screen.getByTestId('for-recruiters')).toBeVisible()
    fireEvent.click(screen.getByTestId('for-candidates'))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(screen.queryByText('CANDIDATE PLATFORM')).not.toBeInTheDocument()
  })

  it('marks legal routes as launch-blocking placeholders', () => {
    window.history.replaceState({}, '', '/privacy')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Privacy Policy placeholder' })).toBeVisible()
    expect(screen.getByText(/not a legal policy/i)).toBeVisible()
  })
})
