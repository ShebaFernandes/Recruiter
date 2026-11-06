import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ForTalent from './ForTalent'

describe('ForTalent', () => {
  it('renders the approved content once and opens the existing candidate entry flow', () => {
    const onJoin = vi.fn()
    const onLogin = vi.fn()
    render(<ForTalent onLogin={onLogin} onJoin={onJoin} />)

    expect(screen.getByRole('heading', { name: 'Join ambitious AI and engineering teams.' })).toBeTruthy()
    expect(screen.getByText(/enter connects talent with companies/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Browse open roles' }).getAttribute('href')).toBe('/opportunities')
    fireEvent.click(screen.getByRole('button', { name: 'Join enter’s Talent network' }))
    expect(onJoin).toHaveBeenCalledOnce()
    expect(onLogin).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(onLogin).toHaveBeenCalledOnce()
  })
})
