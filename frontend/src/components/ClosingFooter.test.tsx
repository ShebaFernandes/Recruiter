import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ClosingFooter from './ClosingFooter'

afterEach(cleanup)

describe('ClosingFooter', () => {
  it('renders the closing banner and verified footer destinations', () => {
    const onCandidate = vi.fn()
    render(<ClosingFooter onCandidate={onCandidate} />)

    expect(screen.getByRole('heading', { name: 'Who are you building next?' })).toBeTruthy()
    expect(screen.getAllByRole('button', { name: /For Candidates/ })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /For Candidates/ }))
    expect(onCandidate).toHaveBeenCalledOnce()

    expect(screen.getByRole('link', { name: 'LinkedIn' })).toHaveAttribute('href', 'https://www.linkedin.com/company/enterrecruitment/posts/?feedView=all')
    expect(screen.getByRole('link', { name: 'Contact' })).toHaveAttribute('href', 'mailto:sheba@enterrecruitment.com')
    expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms')
  })

  it('returns the company call to action to the top of the landing page', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    render(<ClosingFooter onCandidate={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /For Companies/ }))
    expect(window.location.hash).toBe('#enter-home')
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
    scrollTo.mockRestore()
  })

  it('links About to the talent principles section', () => {
    render(<ClosingFooter onCandidate={vi.fn()} />)

    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('href', '#talent-principles')
  })

  it('does not send Opportunities to an unrelated signup screen', () => {
    const onCandidate = vi.fn()
    render(<ClosingFooter onCandidate={onCandidate} />)
    fireEvent.click(screen.getByRole('button', { name: /Opportunities/ }))
    expect(onCandidate).not.toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Opportunities is coming soon.')
  })
})
