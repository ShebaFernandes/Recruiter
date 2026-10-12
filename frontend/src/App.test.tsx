import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
  vi.restoreAllMocks()
})

describe('Enter Talent landing', () => {
  it('opens guest recruiter search directly without a landing login menu', async () => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    render(<App />)
    const entry = await screen.findByTestId('for-recruiters')
    expect(screen.queryByText('Log in')).not.toBeInTheDocument()
    fireEvent.click(entry)
    expect(screen.getByRole('heading', { name: 'Who are we hiring today?' })).toBeVisible()
    expect(screen.queryByLabelText('Company')).not.toBeInTheDocument()
    expect(window.location.pathname).toBe('/recruiter')
    fireEvent.click(screen.getByRole('button', { name: 'Recruiter workspace' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(window.location.pathname).toBe('/recruiter/account')
  })
  it('offers connected recruiter and candidate entry points', async () => {
    render(<App />)
    expect(await screen.findByTestId('for-recruiters')).toBeVisible()
    expect(screen.queryByRole('heading', { name: /Two perspectives/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/The impact we create extends/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Back to top/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Enter recruiter workspace/ })).not.toBeInTheDocument()
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

  it('uses the existing transparent headline mark and direct candidate entry', async () => {
    render(<App />)
    const heading = await screen.findByRole('heading', { name: 'The best teams are built by ENTER.' })
    expect(heading.querySelector('image')).toHaveAttribute('href', '/enter-wordmark.svg')
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).getByRole('button', { name: 'For candidates' }).querySelector('svg')).toBeNull()
    fireEvent.click(within(nav).getByRole('button', { name: 'For candidates' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(window.location.hash).toBe('')
  })
})
