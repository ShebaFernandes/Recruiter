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
beforeEach(() => { vi.useFakeTimers(); vi.spyOn(api, 'candidateProfile').mockResolvedValue(profile) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
async function mount() { await act(async () => { render(<CandidateExperience accountDeleted={vi.fn()} />) }) }
async function upload() { await act(async () => { fireEvent.change(screen.getByTestId('resume-input'), { target: { files: [file] } }) }) }

describe('actual candidate processing integration', () => {
  it('renders accepted uploads immediately, then leaves as soon as a poll completes', async () => {
    vi.spyOn(api, 'uploadResume').mockResolvedValue(queued)
    await mount(); await upload()
    expect(screen.getByRole('heading', { name: "We're doing the boring part." })).toBeVisible()
    expect(screen.getByRole('region', { name: "We're doing the boring part." })).toHaveFocus()
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'My Profile' })).toBeVisible()
  })
  it('handles an already-completed upload response without a minimum loading delay', async () => {
    vi.spyOn(api, 'uploadResume').mockResolvedValue(completed)
    await mount(); await upload()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'My Profile' })).toBeVisible()
  })
  it('returns replacements directly to My Profile with a collapsed contextual conflict action', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(api, 'uploadResume').mockResolvedValue({ ...queued, available_resume: completed.latest_resume, latest_resume: { ...resume, id: 2, version: 2 } })
    await mount()
    fireEvent.click(screen.getByRole('button', { name: /^Career Settings$/ }))
    await upload()
    expect(screen.getByRole('button', { name: /^My Profile$/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('progressbar')).toBeVisible()
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, latest_resume: { ...completed.latest_resume!, id: 2 }, resume_review: { resume_id: 2, fields: { headline: 'New title' } } })
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(screen.queryByRole('heading', { name: 'Review resume changes' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'My Profile' })).toBeVisible()
    expect(document.querySelector('.cp-resume-updates')).not.toHaveAttribute('open')
    expect(screen.getByText('Resume updates (1)')).toBeVisible()
    expect(document.querySelector('.cp-identity')).toHaveTextContent('Engineer')
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
    expect(screen.getByRole('button', { name: /^Career Settings$/ })).toHaveAttribute('aria-current', 'page')
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
    expect(screen.getByRole('heading', { name: 'My Profile' })).toBeVisible()
  })
})
