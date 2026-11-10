import { afterEach, expect, it, vi } from 'vitest'
import { api } from './api'
import { candidateAuthDestination, candidateLanding, finishCandidateLogin, safeCandidateDestination, savedCandidateTab } from './candidateNavigation'
import type { Candidate, User } from './types'

const ready = { profile_status: 'submitted', can_submit: true, latest_resume: { processing_status: 'completed', scan_status: 'clean' } } as Candidate
const user = { id: 5, role: 'candidate' } as User

afterEach(() => { sessionStorage.clear(); window.history.replaceState({}, '', '/'); vi.restoreAllMocks() })

it('opens the existing profile tab for new or incomplete candidates', () => {
  expect(candidateLanding({ profile_status: 'draft', can_submit: false } as Candidate, '/')).toEqual({ path: '/', tab: 'profile' })
  for (const patch of [{ can_submit: false }, { profile_status: 'draft' }, { resume_review: {} }, { resume_identity_warning: { code: 'identity_unverified' } }]) {
    expect(candidateLanding({ ...ready, ...patch } as Candidate, '/').tab).toBe('profile')
  }
})

it('uses existing application readiness for the Opportunities default', () => {
  expect(candidateLanding(ready, '/')).toEqual({ path: '/opportunities', tab: 'opportunities' })
  expect(candidateLanding({ ...ready, profile_completion: { percent: 42 } } as Candidate, '/').tab).toBe('opportunities')
})

it('honors an explicit Opportunities destination even with an incomplete profile', () => {
  expect(candidateLanding({} as Candidate, '/opportunities').tab).toBe('opportunities')
  expect(candidateLanding({} as Candidate, '/opportunities?role=backend-engineer&apply=1').path).toBe('/opportunities?role=backend-engineer&apply=1')
})

it.each(['https://evil.example', '//evil.example', '/recruiter', '/opportunities?role=unknown', '/opportunities?candidate_id=5', '/opportunities?apply=1', '/opportunities?role=backend-engineer&role=ai-ml-engineer'])('rejects unsupported or unauthorized return destinations: %s', next => {
  expect(safeCandidateDestination(next)).toBe('/')
})

it('preserves a selected Apply intent through authentication', () => {
  window.history.replaceState({}, '', '/opportunities')
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  sessionStorage.setItem('enter-opportunity-action', 'apply')
  expect(candidateAuthDestination()).toBe('/opportunities?role=backend-engineer&apply=1')
})

it('keeps landing preferences scoped to the authenticated candidate', async () => {
  vi.spyOn(api, 'candidateProfile').mockResolvedValue({} as Candidate)
  expect(await finishCandidateLogin(user, '/')).toBe('/')
  expect(savedCandidateTab(user.id)).toBe('profile')
  expect(savedCandidateTab(99)).toBeUndefined()
})

it('does not persist a guessed completion result when profile loading fails', async () => {
  vi.spyOn(api, 'candidateProfile').mockRejectedValue(new Error('Temporary failure'))
  await expect(finishCandidateLogin(user, '/')).rejects.toThrow('Temporary failure')
  expect(savedCandidateTab(user.id)).toBeUndefined()
})

it('keeps lightweight navigation IDs synchronized with the existing public catalog', async () => {
  const { roles } = await import('./components/opportunityRoles')
  const { opportunityIds } = await import('./opportunityIds')
  expect(opportunityIds).toEqual(roles.map(role => role.id))
})
