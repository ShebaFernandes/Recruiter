import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TalentPrinciples from './TalentPrinciples'

describe('TalentPrinciples', () => {
  it('renders all principles, evidence examples and timeline stages', () => {
    render(<TalentPrinciples />)

    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain('Getting it')
    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain('an option.')
    expect(screen.getByText('ENGINEERING EVIDENCE.')).toBeTruthy()
    expect(screen.getByText('DEPTH.')).toBeTruthy()
    expect(screen.getByText('COMPLEXITY.')).toBeTruthy()
    expect(screen.getByText('SCOPE.')).toBeTruthy()
    expect(screen.getByText('PROOF.')).toBeTruthy()
    expect(screen.getByText('BOTTLENECK FOUND')).toBeTruthy()
    expect(screen.getByText('PRODUCTION FAILURE')).toBeTruthy()
    expect(screen.getByText('OPTIMIZATION PROVEN')).toBeTruthy()
    expect(screen.getByLabelText('Engineering evidence timeline').textContent).toContain('BUILD')
    expect(screen.getByLabelText('Engineering evidence timeline').textContent).toContain('IMPACT')
  })
})
