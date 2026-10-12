import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Landing from '../Landing'
import CompanyLogoPreview from './CompanyLogoPreview'
import { previewCompanies } from './companies'

afterEach(cleanup)

describe('public company-logo marquee', () => {
  it('appears on the default landing page without preview opt-in', () => {
    window.history.replaceState({}, '', '/')
    render(<Landing choose={vi.fn()} />)
    expect(screen.getByRole('region', { name: 'Company logos' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'About Shiprocket' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'About WazirX' })).toBeVisible()
  })

  it('contains only verified usable artwork from the replacement list', () => {
    expect(previewCompanies.map(c => c.name)).toEqual(['Shiprocket', 'WazirX'])
    expect(previewCompanies.every(c => c.source.startsWith('https://') && c.description && c.category)).toBe(true)
  })

  it('provides one accessible stop per logo and portaled, dismissible details', () => {
    const { container } = render(<CompanyLogoPreview />)
    expect(screen.getAllByRole('button', { name: /^About / })).toHaveLength(2)
    expect(screen.queryByText(/public logo permissions pending/)).not.toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'About Shiprocket' })
    fireEvent.click(button)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('E-commerce logistics')
    expect(container.contains(tooltip)).toBe(false)
    expect(button).toHaveAttribute('aria-describedby', tooltip.id)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.click(button)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('supports tap-to-toggle and an explicit pause control', () => {
    render(<CompanyLogoPreview />)
    const company = screen.getByRole('button', { name: 'About WazirX' })
    fireEvent.click(company)
    expect(screen.getByRole('tooltip')).toHaveTextContent('WazirX')
    fireEvent.click(company)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pause company logos' }))
    expect(screen.getByRole('button', { name: 'Resume company logos' })).toHaveAttribute('aria-pressed', 'true')
  })
})
