import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../api'
import { AuthScreen } from '../PlatformScreens'
import { GoogleButton, GoogleLoginScreen } from './GoogleLogin'

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, '', '/') })

it('keeps Google disabled until enabled by the backend', async () => {
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: false })
  render(<GoogleButton />)
  expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeDisabled()
  expect(await screen.findByText(/Continue with email below/)).toBeInTheDocument()
})

it.each(['login', 'signup'] as const)('makes Google the first candidate %s action and retains password fallback', async mode => {
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: true })
  render(<AuthScreen role="candidate" initialMode={mode} onDone={vi.fn()} back={vi.fn()} />)
  const google = screen.getByRole('button', { name: 'Continue with Google' })
  await waitFor(() => expect(google).toBeEnabled())
  const password = screen.getByLabelText('Password')
  expect(password).not.toBeVisible()
  fireEvent.click(screen.getByText('Continue with email', { exact: true }))
  expect(password).toBeVisible()
  expect(google.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getByLabelText('Email')).toBeInTheDocument()
})

it('leaves recruiter authentication unchanged', () => {
  render(<AuthScreen role="recruiter" onDone={vi.fn()} back={vi.fn()} />)
  expect(screen.queryByRole('button', { name: 'Continue with Google' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
})

it('handles start failures with password fallback available', async () => {
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: true })
  vi.spyOn(api, 'googleStart').mockRejectedValue(new Error('Please retry Google sign-in.'))
  render(<AuthScreen role="candidate" onDone={vi.fn()} back={vi.fn()} />)
  const button = screen.getByRole('button', { name: 'Continue with Google' })
  await waitFor(() => expect(button).toBeEnabled())
  fireEvent.click(button)
  expect(await screen.findByRole('alert')).toHaveTextContent('Please retry Google sign-in.')
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
})

it.each(['cancelled', 'failed'])('shows a retry path after %s', result => {
  window.history.replaceState({}, '', `/auth/google?result=${result}`)
  render(<GoogleLoginScreen />)
  expect(screen.getByRole('link', { name: 'Return to ENTER' })).toHaveAttribute('href', '/')
  expect(screen.getByText(result === 'cancelled' ? /sign-in was cancelled/ : /could not be completed/)).toBeInTheDocument()
})

it('requires the existing password for an email collision', async () => {
  window.history.replaceState({}, '', '/auth/google?result=link')
  vi.spyOn(api, 'googlePending').mockResolvedValue({ stage: 'link', email: 'candidate@example.test', full_name: 'Candidate' })
  const complete = vi.spyOn(api, 'googleComplete')
  const link = vi.spyOn(api, 'googleLinkStart').mockRejectedValue(new Error('Existing password required.'))
  render(<GoogleLoginScreen />)
  fireEvent.change(await screen.findByLabelText('Current ENTER password'), { target: { value: 'synthetic-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verify ENTER account and continue' }))
  await waitFor(() => expect(link).toHaveBeenCalledWith('candidate@example.test', 'synthetic-password', '/'))
  expect(complete).not.toHaveBeenCalled()
  expect(await screen.findByRole('alert')).toHaveTextContent('Existing password required.')
})

it('requires explicit confirmation after verifying both identities', async () => {
  window.history.replaceState({}, '', '/auth/google?result=confirm_link')
  vi.spyOn(api, 'googlePending').mockResolvedValue({ stage: 'confirm_link', email: 'candidate@example.test', full_name: 'Candidate' })
  const confirm = vi.spyOn(api, 'googleLinkConfirm').mockRejectedValue(new Error('Connection expired.'))
  render(<GoogleLoginScreen />)
  const button = await screen.findByRole('button', { name: 'Confirm connection' })
  expect(confirm).not.toHaveBeenCalled()
  fireEvent.click(button)
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection expired.')
})

it('blocks new signup when requirements are unavailable without offering an unchecked completion', async () => {
  window.history.replaceState({}, '', '/auth/google?result=signup')
  vi.spyOn(api, 'googlePending').mockResolvedValue({ stage: 'signup', email: 'synthetic@example.test', full_name: 'Synthetic', signup_available: false })
  const complete = vi.spyOn(api, 'googleComplete')
  render(<GoogleLoginScreen />)
  expect(await screen.findByRole('heading', { name: 'Google signup is not available yet' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Create candidate account' })).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Browse Opportunities' })).toHaveAttribute('href', '/opportunities')
  expect(complete).not.toHaveBeenCalled()
})

it('does not add fallback legal notices or a checkbox', async () => {
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: true })
  render(<GoogleButton />)
  expect(screen.queryByRole('link', { name: 'Terms' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Privacy Policy' })).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})

it('renders the exact approved notice and binds the deliberate button to its version', async () => {
  const text = 'For new accounts, selecting “Continue with Google” means you agree to ENTER’s Terms, declare that you are at least 18, and select India as your registration country. These are your declarations; Google sign-in does not verify your age or registration country for ENTER. Read our Privacy Policy.'
  const notice = { text, version: 'enter-google-signup-notice-draft-02', challenge: 'synthetic-challenge', terms_url: '/api/v1/auth/google/documents/terms/?version=test&sha256=test', privacy_url: '/api/v1/auth/google/documents/privacy/?version=test&sha256=test' }
  vi.spyOn(api, 'googleConfig').mockResolvedValue({ enabled: true, signup_notice: notice })
  const start = vi.spyOn(api, 'googleStart').mockRejectedValue(new Error('Synthetic stop before navigation'))
  render(<GoogleButton />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled())
  expect(screen.getByRole('link', { name: 'Terms' }).closest('small')).toHaveTextContent(text)
  expect(screen.getByRole('link', { name: 'Privacy Policy' }).getAttribute('href')).toContain('/api/v1/auth/google/documents/privacy/')
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(start).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
  await waitFor(() => expect(start).toHaveBeenCalledWith('/', notice))
})

it('offers no completion form even for a stale signup callback', async () => {
  window.history.replaceState({}, '', '/auth/google?result=signup')
  vi.spyOn(api, 'googlePending').mockResolvedValue({ stage: 'signup', email: 'stale@example.test', full_name: 'Stale', signup_available: true })
  render(<GoogleLoginScreen />)
  expect(await screen.findByRole('heading', { name: 'Google signup is not available yet' })).toBeVisible()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Create candidate account' })).not.toBeInTheDocument()
})
