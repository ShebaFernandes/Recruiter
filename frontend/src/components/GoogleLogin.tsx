import { useEffect, useState } from 'react'
import { api, API_URL } from '../api'
import { candidateAuthDestination, finishCandidateLogin, safeCandidateDestination } from '../candidateNavigation'
import { Button, Card, FormField } from './ui'
import './google-login.css'


type GoogleConfiguration = Awaited<ReturnType<typeof api.googleConfig>>
let configurationRequest: Promise<GoogleConfiguration> | undefined
function loadConfiguration() {
  // Share concurrent mounts so a notice cannot be bound to competing browser cookies.
  if (!configurationRequest) configurationRequest = api.googleConfig().finally(() => { configurationRequest = undefined })
  return configurationRequest
}
function documentUrl(path: string) {
  return new URL(path, new URL(API_URL, window.location.origin)).href
}
function SignupNotice({ notice }: { notice: NonNullable<GoogleConfiguration['signup_notice']> }) {
  const [before, afterTerms] = notice.text.split('Terms')
  const [middle, afterPrivacy] = afterTerms.split('Privacy Policy')
  return <small>{before}<a href={documentUrl(notice.terms_url)} target="_blank" rel="noopener noreferrer">Terms</a>{middle}<a href={documentUrl(notice.privacy_url)} target="_blank" rel="noopener noreferrer">Privacy Policy</a>{afterPrivacy}</small>
}
export function GoogleButton() {
  const [configuration, setConfiguration] = useState<GoogleConfiguration>({ enabled: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { let active = true; loadConfiguration().then(result => { if (active) setConfiguration(result) }).catch(() => {}); return () => { active = false } }, [])
  return <div className="google-login"><Button type="button" className="google-signin-button" size="large" fullWidth disabled={!configuration.enabled || busy} onClick={async () => {
    setBusy(true); setError('')
    try { window.location.assign((await api.googleStart(candidateAuthDestination(), configuration.signup_notice)).url) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start Google Login.'); setBusy(false); loadConfiguration().then(setConfiguration).catch(() => {}) }
  }}><span className="google-button-mark" aria-hidden="true"><img src="/google-g.png" width="24" height="24" alt="" /></span><span className="google-button-label">Continue with Google</span></Button>{configuration.signup_notice ? <SignupNotice notice={configuration.signup_notice} /> : <small>Read ENTER’s <a href="/terms" target="_blank" rel="noopener noreferrer">Terms</a> and <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.</small>}{!configuration.enabled && <small>Google Login is not available yet. Continue with email below.</small>}{error && <p role="alert">{error}</p>}</div>
}

export function GoogleLoginScreen() {
  const query = new URLSearchParams(window.location.search)
  const result = query.get('result')
  const next = safeCandidateDestination(query.get('next'))
  const [pending, setPending] = useState<Awaited<ReturnType<typeof api.googlePending>> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const signupUnavailable = pending?.stage === 'signup' || result === 'signup_unavailable'
  useEffect(() => {
    if (result === 'success') {
      let active = true
      api.me().then(user => finishCandidateLogin(user, next)).then(path => { if (active) window.location.replace(path) }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not open your account.') })
      return () => { active = false }
    }
    if (!['signup', 'link', 'confirm_link'].includes(result || '')) return
    let active = true
    api.googlePending().then(value => { if (active) setPending(value) }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Please start again.') })
    return () => { active = false }
  }, [result, next])
  return <main className="auth-page"><Card className="auth-card google-completion">
    <img className="google-enter-logo" src="/enter-logo.jpeg" alt="enter" />
    <h1>{result === 'verification_required' ? 'Check your email' : signupUnavailable ? 'Google signup is not available yet' : pending?.stage === 'confirm_link' ? 'Connect your Google account' : pending?.stage === 'link' ? 'Sign in to connect Google' : result === 'reauthenticated' ? 'Identity confirmed' : 'Continue to ENTER'}</h1>
    {error && <p role="alert" className="error">{error}</p>}
    {result === 'success' && error && <Button onClick={() => window.location.reload()}>Retry opening your account</Button>}
    {result === 'cancelled' && <p>Google sign-in was cancelled. You can try again or use email and password.</p>}
    {result === 'failed' && <p>Google sign-in could not be completed or has expired. Please try again.</p>}
    {result === 'reauthenticated' && <p>Return to account settings to finish your action within five minutes.</p>}
    {result === 'verification_required' && <p>Your account was created. Check your email to verify ownership before signing in. Google does not verify ownership of every third-party mailbox for ENTER. Use ENTER’s resend-verification option if needed.</p>}
    {signupUnavailable && <><p role="status">Google verified your identity. No ENTER account has been created. New candidate signup is unavailable until approved signup requirements are configured.</p><a href="/opportunities">Browse Opportunities</a></>}
    {pending && <>
      <p>{pending.email}</p>
      {pending.stage === 'link' && <form onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError('')
        const data = new FormData(event.currentTarget)
        try { window.location.assign((await api.googleLinkStart(String(data.get('email')), String(data.get('password')), next)).url) }
        catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not connect Google.'); setBusy(false) }
      }}><p>Use your verified ENTER account password, then choose the same Google account and confirm the connection. Your candidate data stays with your existing account.</p><FormField name="email" label="ENTER email" type="email" defaultValue={pending.email} autoComplete="username" required /><FormField name="password" label="Current ENTER password" type="password" autoComplete="current-password" required /><Button fullWidth disabled={busy}>Verify ENTER account and continue</Button><p>Need verification or password recovery? Return to ENTER login below.</p></form>}
      {pending.stage === 'confirm_link' && <><p>Connect this Google identity to the ENTER account you just verified?</p><Button fullWidth disabled={busy} onClick={async () => { setBusy(true); try { const response = await api.googleLinkConfirm(); window.location.replace(await finishCandidateLogin(response.user, next)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not connect Google.'); setBusy(false) } }}>Confirm connection</Button></>}
    </>}
    <a href={next}>Return to ENTER</a>
  </Card></main>
}
