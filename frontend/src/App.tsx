import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { api, auth } from './api'
import { candidateAuthDestination, finishCandidateLogin, clearCandidateLanding, clearCandidateIntent } from './candidateNavigation'
import type { User } from './types'
import Landing from './components/Landing'
import { loadCareers, loadOpportunities } from './publicPageLoader'
import { afterHomepageIntro } from './homepageHydration'

const GoogleLoginScreen = lazy(() => import('./components/GoogleLogin').then(module => ({ default: module.GoogleLoginScreen })))
const PlatformBackground = lazy(() => import('./components/PlatformBackground'))
const Careers = lazy(loadCareers)
const Opportunities = lazy(loadOpportunities)
const AuthScreen = lazy(() => import('./PlatformScreens').then(module => ({ default: module.AuthScreen })))
const EmailVerificationScreen = lazy(() => import('./PlatformScreens').then(module => ({ default: module.EmailVerificationScreen })))
const PasswordResetScreen = lazy(() => import('./PlatformScreens').then(module => ({ default: module.PasswordResetScreen })))
const LegalPlaceholder = lazy(() => import('./PlatformScreens').then(module => ({ default: module.LegalPlaceholder })))
const CandidatePortal = lazy(() => import('./PlatformScreens').then(module => ({ default: module.CandidatePortal })))
const RecruiterPortal = lazy(() => import('./PlatformScreens').then(module => ({ default: module.RecruiterPortal })))

function ScreenBoundary({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<main className="auth-page"><div className="candidate-profile-loading" role="status">Opening Enter…</div></main>}>{children}</Suspense>
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={`brand ${compact ? 'brand-compact' : ''}`}>
    <img src="/enter-logo.jpeg" alt="enter" />
    <span>Talent Platform</span>
  </div>
}


export default function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [choice, setChoice] = useState<'candidate' | 'recruiter' | null>(null)
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup')
  const [accountRemoved, setAccountRemoved] = useState(false)
  // Lets a signed-in user preview the public marketing site from their
  // dashboard header without ending their session.
  const [viewingHome, setViewingHome] = useState(false)
  const screen = useMemo(() => user?.role || choice || (path === '/recruiter' || path === '/recruiter/account' ? 'recruiter' : null), [user, choice, path])
  function navigate(next: string) {
    window.history.pushState({}, '', next)
    setPath(next); setChoice(null); setViewingHome(false)
    window.scrollTo(0, 0)
  }
  function goHome() {
    navigate('/')
    setViewingHome(true)
  }
  useEffect(() => {
    const onBack = () => { setPath(window.location.pathname); setChoice(null); setViewingHome(false) }
    window.addEventListener('popstate', onBack)
    return () => window.removeEventListener('popstate', onBack)
  }, [])
  useEffect(() => {
    let active = true
    const loadAccount = () => {
      if (!active) return
      void api.me().then(value => { if (active) setUser(value) })
        .catch(() => { if (active) setUser(null) })
    }
    const landing = document.querySelector<HTMLElement>('.simple-landing')
    const query = new URLSearchParams(window.location.search)
    if (window.location.pathname === '/' && landing && !query.has('verify-email') && !query.has('reset-password')) {
      // The public intro does not depend on account data. Input releases this wait immediately.
      void afterHomepageIntro(landing).then(loadAccount)
    } else loadAccount()
    return () => { active = false }
  }, [])
  useEffect(() => {
    const expireSession = () => {
      auth.clear()
      setUser(null)
      setChoice(null)
    }
    window.addEventListener('enter-auth-expired', expireSession)
    return () => window.removeEventListener('enter-auth-expired', expireSession)
  }, [])
  async function logout() { try { await api.logout() } catch { /* local logout still applies */ } auth.clear(); clearCandidateLanding(); setUser(null); navigate('/') }
  const query = new URLSearchParams(window.location.search)
  if (import.meta.env.VITE_CANDIDATE_ONLY === 'true' && (path.startsWith('/recruiter') || screen === 'recruiter')) return <ScreenBoundary><PlatformBackground><ScreenBoundary><main className="auth-page"><section className="auth-card"><h1>This platform is not available</h1><button onClick={() => { setUser(null); navigate('/') }}>Return to Enter</button></section></main></ScreenBoundary></PlatformBackground></ScreenBoundary>
  if (path === '/auth/google') return <ScreenBoundary><PlatformBackground><GoogleLoginScreen /></PlatformBackground></ScreenBoundary>
  if (path === '/opportunities' && !choice && user?.role !== 'candidate') return <ScreenBoundary><Opportunities key={user?.role || 'public'} loggedIn={false} onLogin={() => { setAuthMode('login'); setChoice('candidate') }} /></ScreenBoundary>
  if (path === '/careers') return <ScreenBoundary><Careers /></ScreenBoundary>
  if (path === '/privacy') return <ScreenBoundary><LegalPlaceholder kind="privacy" /></ScreenBoundary>
  if (path === '/terms') return <ScreenBoundary><LegalPlaceholder kind="terms" /></ScreenBoundary>
  const verificationToken = query.get('verify-email')
  if (verificationToken) return <ScreenBoundary><PlatformBackground><ScreenBoundary>{<EmailVerificationScreen token={verificationToken} onDone={async payload => { if (payload.user.role === 'candidate') { const next = await finishCandidateLogin(payload.user, candidateAuthDestination()); setUser(payload.user); navigate(next) } else setUser(payload.user) }} />}</ScreenBoundary></PlatformBackground></ScreenBoundary>
  const resetToken = query.get('reset-password')
  if (resetToken) return <ScreenBoundary><PlatformBackground><ScreenBoundary>{<PasswordResetScreen token={resetToken} done={role => { setAuthMode('login'); if (role === 'recruiter') navigate('/recruiter'); else setChoice('candidate'); setUser(null) }} />}</ScreenBoundary></PlatformBackground></ScreenBoundary>
  if (user === undefined && screen) return <ScreenBoundary><PlatformBackground playVideo={false}><ScreenBoundary>{<main className="auth-page"><div className="candidate-profile-loading" role="status">Opening Enter…</div></main>}</ScreenBoundary></PlatformBackground></ScreenBoundary>
  if (accountRemoved) return <ScreenBoundary><PlatformBackground><ScreenBoundary>{<main className="auth-page"><section className="auth-card auth-state-card"><Brand /><div className="auth-state-icon"><CheckCircle2 /></div><h1>Your account has been deleted</h1><p>Your profile is no longer accessible. Private file cleanup has been scheduled securely.</p><button className="primary" onClick={() => { setAccountRemoved(false); setChoice(null) }}>Return to Enter</button></section></main>}</ScreenBoundary></PlatformBackground></ScreenBoundary>
  if (!screen) return <Landing choose={(role, mode = 'signup') => { if (role === 'recruiter') navigate('/recruiter'); else { setAuthMode(mode); setChoice(role) } }} />
  if (!user) return <ScreenBoundary><PlatformBackground><ScreenBoundary>{<AuthScreen role={screen} initialMode={authMode} back={() => { clearCandidateIntent(); navigate('/') }} onDone={async payload => { if (payload.user.role === 'candidate') { const next = await finishCandidateLogin(payload.user, candidateAuthDestination()); setUser(payload.user); navigate(next) } else setUser(payload.user) }} />}</ScreenBoundary></PlatformBackground></ScreenBoundary>
  if (viewingHome) return <Landing choose={(role, mode = 'signup') => { setViewingHome(false); if (role === 'recruiter') navigate('/recruiter'); else { setAuthMode(mode); setChoice(role) } }} />
  return <ScreenBoundary><PlatformBackground><ScreenBoundary>{user.role === 'candidate' ? <CandidatePortal user={user} logout={logout} goHome={goHome} accountDeleted={() => { setUser(null); setChoice(null); setAccountRemoved(true) }} /> : <RecruiterPortal user={user} logout={logout} goHome={goHome} />}</ScreenBoundary></PlatformBackground></ScreenBoundary>
}
