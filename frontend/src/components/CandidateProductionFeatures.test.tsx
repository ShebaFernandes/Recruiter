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

  it('confirms only an unverified exact resume after fresh password entry', async () => {
    const ambiguous = { ...completed, resume_identity_warning: { resume_id: 1, version: 2, original_name: 'career.docx', code: 'identity_unverified', can_confirm: true } }
    vi.mocked(api.candidateProfile).mockResolvedValue(ambiguous)
    const confirmed = vi.spyOn(api, 'confirmResumeOwnership').mockResolvedValue({ ...completed, resume_identity_warning: null })
    await mount()
    expect(screen.getByRole('alert')).toHaveTextContent('Resume version 2: career.docx')
    expect(screen.getByRole('button', { name: 'Confirm ownership' })).toBeDisabled()
    fireEvent.click(screen.getByLabelText('I confirm this exact resume is mine.'))
    fireEvent.change(screen.getByLabelText('Verify your account password'), { target: { value: 'strong-pass-123' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Confirm ownership' })) })
    expect(confirmed).toHaveBeenCalledWith(1, 2, 'strong-pass-123')
    expect(screen.queryByText('Confirm this resume belongs to you')).not.toBeInTheDocument()
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
