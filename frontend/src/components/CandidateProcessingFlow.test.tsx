import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CandidateExperience from './CandidateExperience'
import { api } from '../api'
import type { Candidate, Resume } from '../types'

const resume: Resume = { id: 1, original_name: 'career.docx', version: 1, uploaded_at: '', processing_status: 'queued', scan_status: 'quarantined', processing_error: '', can_retry: false, url: null }
const profile = { id: 1, full_name: 'Test Candidate', headline: 'Engineer', total_experience: '5', skills: ['Python'], work_experiences: [], career_preferences: {}, education: [], work_preferences: [], profile_updated_at: '', meaningful_work: '', latest_resume: null } as unknown as Candidate
const queued = { ...profile, latest_resume: resume }
const completed = { ...profile, latest_resume: { ...resume, processing_status: 'completed', scan_status: 'clean' } as Resume }
const file = new File(['local document'], 'career.docx')
beforeEach(() => { sessionStorage.clear(); vi.useFakeTimers(); vi.spyOn(api, 'candidateProfile').mockResolvedValue(profile) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
async function mount() { await act(async () => { render(<CandidateExperience accountDeleted={vi.fn()} />) }) }
async function upload() { await act(async () => { fireEvent.change(screen.getByTestId('resume-input'), { target: { files: [file] } }) }) }

describe('actual candidate processing integration', () => {
  it('recovers only this candidate’s tab-local unsaved answer and removes it after retry', async () => {
    sessionStorage.setItem('enter:candidate:1:answer-draft', 'Recover my unsaved answer')
    sessionStorage.setItem('enter:candidate:2:answer-draft', 'Another account private answer')
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(api, 'updateCandidate').mockImplementation(async values => ({ ...completed, ...values }))
    await mount()
    expect(screen.getByLabelText("What is the most meaningful thing you've built?")).toHaveValue('Recover my unsaved answer')
    expect(screen.queryByText('Another account private answer')).not.toBeInTheDocument()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry saving answer' })) })
    expect(sessionStorage.getItem('enter:candidate:1:answer-draft')).toBeNull()
    expect(sessionStorage.getItem('enter:candidate:2:answer-draft')).toBe('Another account private answer')
  })
  it('debounces answer saves and serializes newer drafts behind an in-flight write', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(0)
    let finish: (value: Candidate) => void = () => undefined
    const patch = vi.spyOn(api, 'updateCandidate').mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
      .mockImplementation(async values => ({ ...completed, ...values }))
    await mount()
    fireEvent.click(screen.getByRole('button', { name: "That's me ✓" }))
    const answer = screen.getByLabelText("What is the most meaningful thing you've built?")
    fireEvent.change(answer, { target: { value: 'First draft' } })
    await act(() => vi.advanceTimersByTimeAsync(650))
    expect(patch).toHaveBeenCalledTimes(1)
    fireEvent.change(answer, { target: { value: 'Latest complete answer' } })
    await act(() => vi.advanceTimersByTimeAsync(650))
    expect(patch).toHaveBeenCalledTimes(1)
    await act(async () => { finish({ ...completed, meaningful_work: 'First draft' }) })
    expect(patch).toHaveBeenLastCalledWith({ meaningful_work: 'Latest complete answer' })
    expect(answer).toHaveValue('Latest complete answer')
    expect(screen.queryByRole('button', { name: 'Save answer' })).not.toBeInTheDocument()
  })
  it('keeps a failed answer editable, blocks navigation and offers a working retry', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(0)
    const patch = vi.spyOn(api, 'updateCandidate').mockRejectedValue(new Error('Connection unavailable'))
    await mount()
    fireEvent.click(screen.getByRole('button', { name: "That's me ✓" }))
    const answer = screen.getByLabelText("What is the most meaningful thing you've built?")
    fireEvent.change(answer, { target: { value: 'Keep my work' } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Career Settings' })) })
    expect(screen.queryByRole('heading', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(answer).toHaveValue('Keep my work')
    expect(screen.getByRole('button', { name: 'Retry saving answer' })).toBeVisible()
    patch.mockImplementation(async values => ({ ...completed, ...values }))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry saving answer' })) })
    expect(screen.queryByRole('button', { name: 'Retry saving answer' })).not.toBeInTheDocument()
    expect(answer).toHaveValue('Keep my work')
    fireEvent.click(screen.getByRole('button', { name: 'Career Settings' }))
    expect(screen.getByRole('heading', { name: 'Career Settings' })).toBeVisible()
  })
  it('uses compact saved identity details and reveals Beyond the CV only after confirmation', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue({
      ...completed,
      location: 'Bengaluru',
      education: ['Birla Institute of Technology, Mesra — MCA'],
    })
    await mount()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'My Profile' })).not.toBeInTheDocument()
    expect(Array.from(document.querySelectorAll('.cp-identity-meta>span')).map(item => item.textContent)).toEqual(['Birla Institute of Technology, Mesra', '5 years experience', 'Bengaluru'])
    expect(screen.getByRole('heading', { name: 'Your career journey' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Add career history' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'BEYOND THE CV' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: "That's me ✓" }))
    expect(screen.getByRole('heading', { name: 'BEYOND THE CV' })).toBeVisible()
  })
  it('keeps the saved profile and shows an inline correction path for identity mismatch', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, resume_identity_warning: { resume_id: 1, code: 'identity_mismatch' } })
    await mount()
    expect(screen.getByRole('alert')).toHaveTextContent("We couldn't match this resume")
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
    expect(document.querySelector('.cp-identity')).toHaveTextContent('Test Candidate')
    expect(screen.queryByRole('heading', { name: 'Review resume changes' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Choose the correct resume' }))
    expect(screen.getByRole('heading', { name: 'Career Settings' })).toBeVisible()
  })
  it('renders accepted uploads immediately, then leaves as soon as a poll completes', async () => {
    vi.spyOn(api, 'uploadResume').mockResolvedValue(queued)
    await mount(); await upload()
    expect(screen.getByRole('heading', { name: "We're doing the boring part." })).toBeVisible()
    expect(screen.getByRole('region', { name: "We're doing the boring part." })).toHaveFocus()
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
  })
  it('handles an already-completed upload response without a minimum loading delay', async () => {
    vi.spyOn(api, 'uploadResume').mockResolvedValue(completed)
    await mount(); await upload()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
  })
  it('returns replacements directly to My Profile with a collapsed contextual conflict action', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(api, 'uploadResume').mockResolvedValue({ ...queued, available_resume: completed.latest_resume, latest_resume: { ...resume, id: 2, version: 2 } })
    await mount()
    fireEvent.click(screen.getByRole('button', { name: /^Career Settings$/ }))
    await upload()
    expect(screen.getByRole('button', { name: /^Career Settings$/ })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('progressbar')).toBeVisible()
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, latest_resume: { ...completed.latest_resume!, id: 2 }, resume_review: { resume_id: 2, fields: { headline: 'New title' } } })
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.queryByRole('heading', { name: 'Review resume changes' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
    expect(document.querySelector('.cp-resume-updates')).not.toHaveAttribute('open')
    expect(screen.getByText('New resume changes to review (1)')).toBeVisible()
    expect(document.querySelector('.cp-identity')).toHaveTextContent('Engineer')
  })
  it('shows a role-level career comparison before applying protected resume history', async () => {
    const saved = [
      { company: 'Old Studio', role: 'Engineer', start_date: '2018-01-01', end_date: '2020-01-01', date_label: '2018 - 2020', description: '', gap_reason: '' },
    ]
    const proposed = Array.from({ length: 7 }, (_, index) => ({
      company: index < 3 ? 'Northstar' : index < 6 ? 'Earlier Studio' : 'First Company',
      role: `Role ${index + 1}`,
      start_date: `${2011 + index}-01-01`,
      end_date: `${2012 + index}-01-01`,
      date_label: `${2011 + index} - ${2012 + index}`,
      description: '', gap_reason: '',
    }))
    vi.mocked(api.candidateProfile).mockResolvedValue({
      ...completed,
      work_experiences: saved,
      resume_review: { resume_id: 2, original_name: 'complete-career.docx', fields: { work_experiences: proposed } },
    })
    vi.spyOn(api, 'reviewResume').mockResolvedValue({ ...completed, work_experiences: proposed, resume_review: null })
    await mount()
    fireEvent.click(screen.getByText('New resume changes to review (1)'))
    expect(screen.getByText(/saved profile has 1 roles; the latest resume contains 7 roles across 3 employers/i)).toBeVisible()
    expect(screen.getByText('Role 7')).toBeVisible()
    fireEvent.click(screen.getByLabelText('Use these 7 roles in my Career Journey'))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Apply selected changes' })) })
    expect(api.reviewResume).toHaveBeenCalledWith(2, ['work_experiences'], '', true)
  })
  it('recovers from polling failure and stops loading on terminal failure', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(queued)
    await mount()
    vi.mocked(api.candidateProfile).mockRejectedValue(new Error('Failed to fetch'))
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.getByRole('status')).toHaveTextContent('Unable to check')
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...queued, latest_resume: { ...resume, processing_status: 'failed', can_retry: true } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Check status again' })) })
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry processing' })).toBeVisible()
  })
  it('does not navigate away or clear state when the upload is rejected', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(api, 'uploadResume').mockRejectedValue(new Error('Upload failed. Please try again.'))
    await mount()
    fireEvent.click(screen.getByRole('button', { name: /^Career Settings$/ }))
    await upload()
    expect(screen.getByRole('button', { name: /^Career Settings$/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('heading', { name: 'Career Settings' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Upload failed')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
  it('times out a stalled status request and resumes polling instead of getting stuck', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(queued)
    await mount()
    vi.mocked(api.candidateProfile).mockImplementation(signal => new Promise((_, reject) => {
      signal?.addEventListener('abort', () => reject(new Error('Request timed out')))
    }))
    await act(() => vi.advanceTimersByTimeAsync(10_750))
    expect(screen.getByRole('status')).toHaveTextContent('Unable to check')
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
  })
})
