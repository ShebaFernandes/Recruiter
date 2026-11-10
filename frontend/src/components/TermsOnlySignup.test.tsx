import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  vi.stubEnv('VITE_CANDIDATE_SIMPLE_SIGNUP', 'true')
  vi.stubEnv('VITE_LEGAL_CONTENT_APPROVED', 'true')
})
import { api } from '../api'
import { AuthScreen } from '../PlatformScreens'
import { LegalChecks } from './LegalReview'
import type { LegalDocuments } from '../legalReview'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(p => [p, {
  text: 'Synthetic document', version: p + '-synthetic', sha256: 'synthetic-hash', unpublished: false,
}])) as LegalDocuments
const configuration = { enabled: true, simple_signup: true, signup_notice: {
  text: '',
  version: 'terms-only-synthetic', challenge: 'synthetic-challenge',
  terms_url: '/terms', privacy_url: '/privacy',
} }
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('email signup has no age/country/checkbox and submits only the actual signup action', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'googleConfig').mockResolvedValue(configuration)
  const signup = vi.spyOn(api, 'signup').mockResolvedValue({ detail: 'Check email', requires_email_verification: true })
  render(<AuthScreen role="candidate" initialMode="signup" onDone={vi.fn()} back={vi.fn()} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled())
  fireEvent.click(screen.getByText('Continue with email', { exact: true }))
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(document.querySelector('input[name="country_code"]')).not.toBeInTheDocument()
  expect(screen.queryByText(/at least 18|These are your declarations/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Synthetic Candidate' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'synthetic@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Synthetic-password-123!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
  await waitFor(() => expect(signup).toHaveBeenCalledOnce())
  const body = signup.mock.calls[0][0]
  expect(body).toMatchObject({ notice_challenge: 'synthetic-challenge', notice_version: 'terms-only-synthetic' })
  for (const key of ['age_accepted', 'age_version', 'country_code', 'terms_accepted']) expect(body).not.toHaveProperty(key)
})

it('simple signup review renders no legal notice or acceptance fields', () => {
  render(<LegalChecks documents={documents} />)
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.queryByText(/By continuing|Privacy Policy/)).not.toBeInTheDocument()
  expect(document.querySelector('input[name="age_version"]')).not.toBeInTheDocument()
})
