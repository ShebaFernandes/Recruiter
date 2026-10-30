import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api'

beforeEach(() => {
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
  vi.restoreAllMocks()
})

describe('Enter Talent landing', () => {
  it('keeps ordered text navigation and hero entry buttons', async () => {
    render(<App />)
    await screen.findByTestId('for-recruiters')
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(Array.from(nav.children).map(item => item.matches('details')
      ? item.querySelector('summary')?.textContent
      : item.textContent)).toEqual([
      'For Recruiters',
      'For Companies',
      'For Candidates',
    ])
    for (const name of ['For Companies', 'For Candidates']) {
      expect(screen.getAllByRole('button', { name })).toHaveLength(3)
      expect(within(nav).getByRole('button', { name })).toBeVisible()
    }
    const hero = within(document.querySelector('.ce-intro') as HTMLElement)
    expect(hero.getByRole('button', { name: 'For Companies' })).toBeVisible()
    expect(hero.getByRole('button', { name: 'For Candidates' })).toBeVisible()
    expect(document.querySelector('.ce-hero-actions')).toBeNull()
    expect(document.querySelector('.ce-preview-interface')).toBeNull()
    expect(document.querySelector('.enter-intro-shell')).toBeNull()
    expect(screen.queryByRole('button', { name: /Skip intro/ })).not.toBeInTheDocument()
  })

  it('opens the hiring section from both company controls', async () => {
    render(<App />)
    const headerCompany = await screen.findByTestId('for-companies')
    const heroCompany = within(document.querySelector('.ce-intro') as HTMLElement).getByRole('button', { name: 'For Companies' })

    const target = document.getElementById('what-building-title') as HTMLElement
    target.scrollIntoView = vi.fn()
    for (const companyControl of [headerCompany, heroCompany]) {
      window.history.replaceState({}, '', '/')
      fireEvent.click(companyControl)
      expect(window.location.hash).toBe('#what-building-title')
      expect(target.scrollIntoView).toHaveBeenCalled()
      expect(screen.getByRole('tab', { name: 'Hire Talent' })).toHaveAttribute('aria-selected', 'true')
      expect(window.location.pathname).toBe('/')
      expect(screen.queryByRole('heading', { name: 'Welcome back' })).not.toBeInTheDocument()
    }
  })
  it('opens the existing candidate signup from the For Talent section', async () => {
    render(<App />)
    const forTalent = (await screen.findByRole('heading', { name: "Let's find work that feels great." })).closest('section') as HTMLElement
    fireEvent.click(within(forTalent).getByRole('button', { name: 'Join ENTER’s talent network' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(window.location.pathname).toBe('/')
  })
  it('opens the workspace directly for a valid recruiter session', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ id: 9, role: 'recruiter', email: 'test@example.com', full_name: 'Approved Recruiter' })
    vi.spyOn(api, 'searches').mockResolvedValue([])
    vi.spyOn(api, 'projects').mockResolvedValue([])
    vi.spyOn(api, 'notifications').mockResolvedValue([])
    window.history.replaceState({}, '', '/recruiter')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Who are we hiring today?' })).toBeVisible()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
  })

  it('opens recruiter login without public signup or a guest search', async () => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    render(<App />)
    const entry = await screen.findByTestId('for-recruiters')
    expect(entry).toHaveTextContent('For Recruiters')
    expect(screen.queryByText('Log in')).not.toBeInTheDocument()
    fireEvent.click(entry)
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    expect(screen.queryByLabelText('Company')).not.toBeInTheDocument()
    expect(window.location.pathname).toBe('/recruiter')
    expect(screen.queryByRole('button', { name: /Create an account/i })).not.toBeInTheDocument()
  })
  it('offers connected recruiter and candidate entry points', async () => {
    render(<App />)
    expect(await screen.findByTestId('for-recruiters')).toBeVisible()
    expect(screen.queryByRole('heading', { name: /Two perspectives/ })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /The impact we create extends across entire organizations/i })).toBeVisible()
    expect(screen.queryByRole('link', { name: /Back to top/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Enter recruiter workspace/ })).not.toBeInTheDocument()
    fireEvent.click(await screen.findByTestId('for-candidates'))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(screen.queryByText('CANDIDATE PLATFORM')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Country')).not.toBeInTheDocument()
    expect(document.querySelector('input[name="country_code"]')).toHaveValue('IN')
    expect(screen.queryByRole('link', { name: 'Privacy Policy' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Terms of Use' })).not.toBeInTheDocument()
  })

  it('fails closed when approved legal publication is unavailable', () => {
    window.history.replaceState({}, '', '/privacy')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Privacy Policy unavailable' })).toBeVisible()
    expect(screen.getByText(/Registration remains disabled/i)).toBeVisible()
  })

  it('uses the existing transparent headline mark and direct candidate entry', async () => {
    render(<App />)
    const heading = await screen.findByRole('heading', { name: 'The best teams are built by ENTER.' })
    expect(heading.querySelector('image')).toHaveAttribute('href', '/enter-wordmark.svg')
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).getByRole('button', { name: 'For Candidates' })).toBeVisible()
    expect(within(nav).getByRole('button', { name: 'For Candidates' }).querySelector('svg')).toBeNull()
    fireEvent.click(within(nav).getByRole('button', { name: 'For Candidates' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    expect(window.location.hash).toBe('')
  })
})
