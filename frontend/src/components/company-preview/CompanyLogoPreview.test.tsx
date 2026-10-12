import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { isCompanyPreviewAllowed } from '../companyPreviewGate'
import CompanyLogoPreview from './CompanyLogoPreview'
import { previewCompanies } from './companies'

afterEach(cleanup)

describe('private company-logo preview', () => {
  it('requires development, a loopback hostname and explicit opt-in', () => {
    expect(isCompanyPreviewAllowed(true, '127.0.0.1', '?preview=company-logos')).toBe(true)
    expect(isCompanyPreviewAllowed(true, 'localhost', '?preview=company-logos')).toBe(true)
    expect(isCompanyPreviewAllowed(true, '[::1]', '?preview=company-logos')).toBe(true)
    expect(isCompanyPreviewAllowed(false, '127.0.0.1', '?preview=company-logos')).toBe(false)
    expect(isCompanyPreviewAllowed(true, 'enter.example.com', '?preview=company-logos')).toBe(false)
    expect(isCompanyPreviewAllowed(true, '127.0.0.1', '')).toBe(false)
    expect(isCompanyPreviewAllowed(true, 'localhost.evil.example', '?preview=company-logos')).toBe(false)
  })

  it('contains exactly the ten selected companies, each with official provenance', () => {
    expect(previewCompanies.map(c => c.name)).toEqual(['Shiprocket', 'Bitscale AI', 'Incubyte',
      'Bridgetown Research', 'Doqfy', 'PeepalCo', 'Anthriq', 'ToneTag', 'Navadhan', 'WazirX'])
    expect(previewCompanies.every(c => c.source.startsWith('https://') && c.description && c.category)).toBe(true)
  })

  it('provides one accessible stop per logo and portaled, dismissible details', () => {
    const { container } = render(<CompanyLogoPreview />)
    expect(screen.getAllByRole('button', { name: /^About / })).toHaveLength(10)
    expect(screen.getByText(/public logo permissions pending/)).toBeVisible()
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
    const company = screen.getByRole('button', { name: 'About Incubyte' })
    fireEvent.click(company)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Incubyte')
    fireEvent.click(company)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pause company logos' }))
    expect(screen.getByRole('button', { name: 'Resume company logos' })).toHaveAttribute('aria-pressed', 'true')
  })
})
