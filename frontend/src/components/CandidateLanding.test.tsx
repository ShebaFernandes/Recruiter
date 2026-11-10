import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CandidatePortal } from '../PlatformScreens'
import { finishCandidateLogin } from '../candidateNavigation'
import { api } from '../api'
import type { Candidate, User } from '../types'

vi.mock('./CandidateExperience', () => ({ default: () => <h2>Existing My Profile view</h2> }))
vi.mock('./Opportunities', () => ({ default: () => <h2>Browse Opportunities</h2> }))
const user = { id: 7, full_name: 'Synthetic Candidate', role: 'candidate', email: 'synthetic@example.test' } as User
const portal = () => <CandidatePortal user={user} logout={vi.fn()} accountDeleted={vi.fn()} goHome={vi.fn()} />
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks() })

it('opens the existing profile tab after an incomplete candidate signs in', async () => {
  vi.spyOn(api, 'candidateProfile').mockResolvedValue({ profile_status: 'draft', can_submit: false } as Candidate)
  await finishCandidateLogin(user, '/')
  render(portal())
  expect(await screen.findByRole('heading', { name: 'Existing My Profile view' })).toBeVisible()
})

it('opens Opportunities when an incomplete candidate explicitly requested browsing', async () => {
  vi.spyOn(api, 'candidateProfile').mockResolvedValue({ profile_status: 'draft', can_submit: false } as Candidate)
  await finishCandidateLogin(user, '/opportunities')
  render(portal())
  expect(await screen.findByRole('heading', { name: 'Browse Opportunities' })).toBeVisible()
})
