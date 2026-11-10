import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => { vi.stubEnv('VITE_LEGAL_CONTENT_APPROVED', 'true') })
import { AuthScreen } from '../PlatformScreens'
import { api } from '../api'
import type { LegalDocuments } from '../legalReview'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('blocks signup when current legal documents cannot load', async () => {
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: false })
  vi.spyOn(api, 'legalDocuments').mockRejectedValue(new Error('Unavailable'))
  const signup = vi.spyOn(api, 'signup')
  render(<AuthScreen role="candidate" back={vi.fn()} onDone={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled()
  expect(await screen.findByText(/Legal documents could not load/)).toBeInTheDocument()
  fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form')!)
  expect(signup).not.toHaveBeenCalled()
})

it('records only explicit candidate signup confirmations with current versions', async () => {
  const documents = Object.fromEntries(['age', 'terms', 'privacy', 'submission'].map(purpose => [purpose, {
    text: `${purpose} synthetic publication`, version: `${purpose}-v1`, sha256: 'synthetic-hash', unpublished: false,
  }])) as LegalDocuments
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: false })
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  const signup = vi.spyOn(api, 'signup').mockResolvedValue({ requires_email_verification: true, detail: 'Synthetic verification only.' })
  render(<AuthScreen role="candidate" back={vi.fn()} onDone={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Synthetic Candidate' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'candidate@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Synthetic-password-123!' } })
  fireEvent.click(await screen.findByRole('checkbox'))
  fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form')!)
  await waitFor(() => expect(signup).toHaveBeenCalledWith(expect.objectContaining({
    email: 'candidate@example.test', role: 'candidate', age_accepted: true, terms_accepted: true,
    age_version: 'age-v1', terms_version: 'terms-v1',
  })))
  expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeVisible()
})
