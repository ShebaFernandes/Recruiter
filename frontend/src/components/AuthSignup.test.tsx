import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => { vi.stubEnv('VITE_LEGAL_CONTENT_APPROVED', 'true') })
import { AuthScreen } from '../PlatformScreens'
import { api } from '../api'
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('creates an account with identity fields only and does not fabricate confirmations', async () => {
  const documents = vi.spyOn(api, 'legalDocuments').mockRejectedValue(new Error('Unavailable'))
  const signup = vi.spyOn(api, 'signup').mockResolvedValue({ requires_email_verification: true, detail: 'Synthetic verification only.' })
  render(<AuthScreen role="candidate" back={vi.fn()} onDone={vi.fn()} />)
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('group', { name: 'Required confirmations' })).not.toBeInTheDocument()
  expect(screen.queryByText(/By creating an account/)).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Terms of Use' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Synthetic Candidate' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'candidate@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Synthetic-password-123!' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form')!)
  await waitFor(() => expect(signup).toHaveBeenCalledWith({ full_name: 'Synthetic Candidate', email: 'candidate@example.test', password: 'Synthetic-password-123!', country_code: 'IN', role: 'candidate' }))
  expect(documents).not.toHaveBeenCalled()
  expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeVisible()
})
