import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AmbitionHires, { ambitionHireResults } from './AmbitionHires'

describe('AmbitionHires', () => {
  it('renders the centralized reference results', () => {
    render(<AmbitionHires />)

    expect(screen.getByRole('heading', { name: 'From ambition to hires.' })).toBeTruthy()
    expect(ambitionHireResults).toHaveLength(6)
    ambitionHireResults.forEach(result => {
      expect(screen.getByText(result.role)).toBeTruthy()
      expect(screen.getByText(result.company)).toBeTruthy()
    })

  })
})
