import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import Landing from './Landing'

afterEach(() => { cleanup(); vi.unstubAllEnvs() })
it('hides recruiter entry points while retaining candidate entry in candidate-only builds', () => {
  vi.stubEnv('VITE_CANDIDATE_ONLY', 'true')
  const choose = vi.fn()
  render(<Landing choose={choose} />)
  expect(screen.queryByTestId('for-recruiters')).not.toBeInTheDocument()
  expect(screen.queryByText('Recruiter log in')).not.toBeInTheDocument()
  expect(screen.getByTestId('for-candidates')).toBeVisible()
  screen.getByRole('button', { name: 'Upload your resume' }).click()
  expect(choose).toHaveBeenCalledWith('candidate')
})
it('preserves recruiter navigation when disabled', () => {
  vi.stubEnv('VITE_CANDIDATE_ONLY', 'false')
  render(<Landing choose={vi.fn()} />)
  expect(screen.getByTestId('for-recruiters')).toBeVisible()
})
