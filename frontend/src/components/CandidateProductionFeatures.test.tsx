import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import CandidateExperience from './CandidateExperience'
import { api } from '../api'
import type { Candidate, Resume } from '../types'

const resume: Resume = { id: 1, original_name: 'career.docx', version: 1, uploaded_at: '', processing_status: 'queued', scan_status: 'quarantined', processing_error: '', can_retry: false, url: null }
const profile = { id: 1, full_name: 'Test Candidate', headline: 'Engineer', total_experience: '5', skills: ['Python'], work_experiences: [], career_preferences: {}, education: [], work_preferences: [], profile_updated_at: '', meaningful_work: '', latest_resume: null } as unknown as Candidate
const completed = { ...profile, latest_resume: { ...resume, processing_status: 'completed', scan_status: 'clean' } as Resume }
beforeEach(() => { sessionStorage.clear(); vi.useFakeTimers(); vi.spyOn(Math, 'random').mockReturnValue(0); vi.spyOn(api, 'candidateProfile').mockResolvedValue(profile); vi.spyOn(api, 'resumeStatus').mockResolvedValue({ resume: completed.latest_resume, worker_available: true }) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
async function mount() { await act(async () => { render(<CandidateExperience accountDeleted={vi.fn()} />) }) }

it('does not show the removed ownership form or automatically confirm a resume', async () => {
  vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, resume_identity_warning: { resume_id: 1, version: 2, original_name: 'career.docx', code: 'identity_unverified', can_confirm: true } })
  const confirm = vi.spyOn(api, 'confirmResumeOwnership')
  await mount()
  expect(screen.queryByText('Confirm this resume belongs to you')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Confirm ownership' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Verify your account password')).not.toBeInTheDocument()
  expect(confirm).not.toHaveBeenCalled()
})

it('saves an inline role edit through the existing API without replacing profile fields', async () => {
  const role = { id: 77, company: 'Synthetic Studio', role: 'Engineer', start_date: '2020-01-01', end_date: '2022-01-01', is_current: false, description: 'Keep this evidence', gap_reason: '' }
  const saved = { ...completed, headline: 'Keep headline', skills: ['Python'], work_experiences: [role] } as Candidate
  vi.mocked(api.candidateProfile).mockResolvedValue(saved)
  const update = vi.spyOn(api, 'updateEmployment').mockResolvedValue({ ...saved, work_experiences: [{ ...role, company: 'Updated Studio' }] })
  await mount()
  fireEvent.click(screen.getByRole('button', { name: /Engineer at Synthetic Studio/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Edit this role' }))
  fireEvent.change(screen.getByLabelText('Employer'), { target: { value: 'Updated Studio' } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Save' })) })
  expect(update).toHaveBeenCalledWith(77, { company: 'Updated Studio' })
  expect(screen.getByText('Keep headline')).toBeVisible()
  expect(saved.work_experiences[0].company).toBe('Synthetic Studio')
  expect(saved.work_experiences[0].description).toBe('Keep this evidence')
})
