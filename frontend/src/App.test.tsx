import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
})

describe('Enter Talent landing', () => {
  it('offers connected recruiter and candidate entry points', async () => {
    render(<App />)
    expect(await screen.findByTestId('for-recruiters')).toBeVisible()
    fireEvent.click(await screen.findByTestId('for-candidates'))
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
