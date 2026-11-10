import { api } from './api'
import { applicationProfileReady } from './opportunityApplication'
import { opportunityIds } from './opportunityIds'
import type { Candidate, User } from './types'

export type CandidateTab = 'profile' | 'opportunities' | 'applications'
const landingKey = 'enter-candidate-landing'
const roleExists = (id: string) => opportunityIds.some(role => role === id)

// Only public opportunity identifiers and UI intent are accepted; never an arbitrary return URL.
export function safeCandidateDestination(value: string | null | undefined) {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/'
  const url = new URL(value, window.location.origin)
  if (url.origin !== window.location.origin || url.hash || url.pathname !== '/opportunities') return '/'
  if ([...url.searchParams.keys()].some(key => !['role', 'apply'].includes(key))) return '/'
  if (url.searchParams.getAll('role').length > 1 || url.searchParams.getAll('apply').length > 1) return '/'
  const role = url.searchParams.get('role')
  const apply = url.searchParams.get('apply')
  if ((url.searchParams.has('role') && (!role || !roleExists(role))) || (url.searchParams.has('apply') && (apply !== '1' || !role))) return '/'
  const query = new URLSearchParams()
  if (role) query.set('role', role)
  if (apply) query.set('apply', apply)
  return '/opportunities' + (query.size ? `?${query}` : '')
}

export function candidateAuthDestination() {
  const current = safeCandidateDestination(window.location.pathname + window.location.search)
  const role = sessionStorage.getItem('enter-opportunity-intent')
  if (role && roleExists(role) && sessionStorage.getItem('enter-opportunity-action') === 'apply') {
    return safeCandidateDestination(`/opportunities?role=${encodeURIComponent(role)}&apply=1`)
  }
  return current
}

export function candidateLanding(profile: Candidate, intended: string) {
  const next = safeCandidateDestination(intended)
  if (next !== '/') return { path: next, tab: 'opportunities' as const }
  return applicationProfileReady(profile)
    ? { path: '/opportunities', tab: 'opportunities' as const }
    : { path: '/', tab: 'profile' as const }
}

export async function finishCandidateLogin(user: User, intended: string) {
  if (user.role !== 'candidate') throw new Error('Sign in with a candidate account to continue.')
  const landing = candidateLanding(await api.candidateProfile(), intended)
  sessionStorage.setItem(landingKey, JSON.stringify({ userId: user.id, tab: landing.tab }))
  clearCandidateIntent()
  return landing.path
}

export function savedCandidateTab(userId: number): CandidateTab | undefined {
  try {
    const value = JSON.parse(sessionStorage.getItem(landingKey) || 'null')
    return value?.userId === userId && ['profile', 'opportunities', 'applications'].includes(value.tab)
      ? value.tab as CandidateTab : undefined
  } catch { return undefined }
}

export function clearCandidateLanding() { sessionStorage.removeItem(landingKey) }

export function clearCandidateIntent() {
  sessionStorage.removeItem('enter-opportunity-intent')
  sessionStorage.removeItem('enter-opportunity-action')
}
