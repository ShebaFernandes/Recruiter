import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CandidateExperience from './CandidateExperience'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import { api } from '../api'
import type { Candidate, Resume } from '../types'

const resume: Resume = { id: 1, original_name: 'career.docx', version: 1, uploaded_at: '', processing_status: 'queued', scan_status: 'quarantined', processing_error: '', can_retry: false, url: null }
const profile = { id: 1, full_name: 'Test Candidate', headline: 'Engineer', total_experience: '5', skills: ['Python'], work_experiences: [], career_preferences: {}, education: [], work_preferences: [], profile_updated_at: '', meaningful_work: '', latest_resume: null } as unknown as Candidate
const queued = { ...profile, latest_resume: resume }
const completed = { ...profile, latest_resume: { ...resume, processing_status: 'completed', scan_status: 'clean' } as Resume }
const file = new File(['local document'], 'career.docx')
beforeEach(() => { sessionStorage.clear(); vi.useFakeTimers(); vi.spyOn(Math, 'random').mockReturnValue(0); vi.spyOn(api, 'candidateProfile').mockResolvedValue(profile); vi.spyOn(api, 'resumeStatus').mockResolvedValue({ resume: completed.latest_resume, worker_available: true }) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
async function mount() { await act(async () => { render(<CandidateExperience accountDeleted={vi.fn()} />) }) }
async function upload() { await act(async () => { fireEvent.change(screen.getByTestId('resume-input'), { target: { files: [file] } }) }) }

describe('actual candidate processing integration', () => {
  it('keeps omitted saved employment visible without a generic review action', () => {
    const items = [
      { id: 1, company: 'Orchid Labs', role: 'Engineering Intern', start_date: '2026-01-01', end_date: '2026-07-01', is_current: false, confidence_status: 'candidate_confirmed' },
      { id: 2, company: 'Cedar Studio', role: 'Developer', start_date: '2026-09-01', end_date: null, is_current: true, confidence_status: 'candidate_confirmed' },
    ] as Candidate['work_experiences']
    const extraction = { resume_id: 2, status: 'verified_ai', source: 'ai', reason_code: 'evidence_roles_accepted', accepted_role_count: 1, saved_role_count: 2, verified_role_ids: [1], unverified_role_ids: [2], candidate_confirmed_role_ids: [1, 2], stale_profile_preserved: true, profile_state: 'previous_history_preserved' } as Candidate['employment_extraction']
    render(<CandidateCareerTimeline items={items} extraction={extraction} edit={vi.fn()} />)
    expect(document.querySelectorAll('.career-period')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Review saved profile' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Developer at Cedar Studio/ })).toHaveAttribute('aria-label', expect.stringContaining('Not matched to the latest resume'))
  })
  it('hides the saved layout during transfer and restores it if upload fails', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    let rejectUpload: (reason: Error) => void = () => undefined
    vi.spyOn(api, 'uploadResume').mockImplementation(() => new Promise((_, reject) => { rejectUpload = reject }))
    await mount()
    await act(async () => { fireEvent.change(screen.getByTestId('resume-input'), { target: { files: [file] } }) })
    expect(screen.getByText('Uploading — transferring your file securely.')).toBeVisible()
    expect(screen.queryByRole('complementary', { name: 'Career Settings panel' })).not.toBeInTheDocument()
    await act(async () => { rejectUpload(new Error('Upload unavailable')) })
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Upload unavailable')
  })
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
  it('keeps a failed answer editable and offers a working retry with persistent settings', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(0)
    const patch = vi.spyOn(api, 'updateCandidate').mockRejectedValue(new Error('Connection unavailable'))
    await mount()
    fireEvent.click(screen.getByRole('button', { name: "That's me ✓" }))
    const answer = screen.getByLabelText("What is the most meaningful thing you've built?")
    fireEvent.change(answer, { target: { value: 'Keep my work' } })
    await act(async () => { fireEvent.blur(answer) })
    expect(screen.queryByRole('heading', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(answer).toHaveValue('Keep my work')
    expect(screen.getByRole('button', { name: 'Retry saving answer' })).toBeVisible()
    patch.mockImplementation(async values => ({ ...completed, ...values }))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry saving answer' })) })
    expect(screen.queryByRole('button', { name: 'Retry saving answer' })).not.toBeInTheDocument()
    expect(answer).toHaveValue('Keep my work')
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
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
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Build ↔ Lead Spectrum' })).toBeVisible()
    expect(screen.queryByText('Role & direction')).not.toBeInTheDocument()
    expect(Array.from(document.querySelectorAll('.cp-identity-meta>span')).map(item => item.textContent)).toEqual(['Birla Institute of Technology, Mesra', '5 years experience', 'Bengaluru'])
    expect(screen.getByRole('heading', { name: 'Your career journey' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Review saved profile' })).not.toBeInTheDocument()
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
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
  })
  it('renders accepted uploads immediately, then leaves as soon as a poll completes', async () => {
    vi.spyOn(api, 'uploadResume').mockResolvedValue(queued)
    await mount(); await upload()
    expect(screen.getByRole('heading', { name: "While we get to know you…" })).toBeVisible()
    expect(screen.getByRole('region', { name: "While we get to know you…" })).toHaveFocus()
    expect(screen.queryByRole('complementary', { name: 'Career Settings panel' })).not.toBeInTheDocument()
    expect(document.querySelector('.cp-profile-workspace')).not.toBeInTheDocument()
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    await act(() => vi.advanceTimersByTimeAsync(3000))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
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
    await upload()
    expect(screen.queryByRole('button', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeVisible()
    expect(screen.queryByRole('complementary', { name: 'Career Settings panel' })).not.toBeInTheDocument()
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, latest_resume: { ...completed.latest_resume!, id: 2 }, resume_review: { resume_id: 2, fields: { headline: 'New title' } } })
    await act(() => vi.advanceTimersByTimeAsync(3000))
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
    fireEvent.click(screen.getByLabelText('Apply these 7 role changes'))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Apply selected changes' })) })
    expect(api.reviewResume).toHaveBeenCalledWith(2, ['work_experiences'], '', true)
  })
  it('opens the pending resume comparison from a conflicting saved Career Journey', async () => {
    const saved = [
      { id: 1, company: 'Cedar Recruitment', role: 'AI Developer', start_date: '2026-09-01',
        end_date: null, is_current: false, date_label: '2026-09-01 — End not specified',
        description: '', gap_reason: '', confidence_status: 'candidate_confirmed' as const },
      { id: 2, company: 'Orchid Research', role: 'AI Intern', start_date: '2026-01-01',
        end_date: '2026-07-01', is_current: false, date_label: 'Jan 2026 - Jul 2026',
        description: '', gap_reason: '', confidence_status: 'candidate_confirmed' as const },
    ]
    const proposed = [{ ...saved[0], is_current: true, date_label: 'Sep 2026 - Present' }, saved[1]]
    vi.mocked(api.candidateProfile).mockResolvedValue({
      ...completed,
      work_experiences: saved,
      employment_extraction: {
        resume_id: 2, status: 'verified_fallback', source: 'rules', reason_code: 'evidence_roles_accepted',
        accepted_role_count: 2, saved_role_count: 2, profile_state: 'pending_candidate_review',
        stale_profile_preserved: true, verified_role_ids: [], candidate_confirmed_role_ids: [1, 2],
        unverified_role_ids: [1, 2],
      },
      resume_review: { resume_id: 2, original_name: 'fictional.docx', fields: { work_experiences: proposed } },
    })
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { callback(0); return 1 })
    const reviewRequest = vi.spyOn(api, 'reviewResume')
    await mount()
    const review = document.getElementById('resume-changes-review') as HTMLDetailsElement
    review.scrollIntoView = vi.fn()
    expect(review).not.toHaveAttribute('open')
    expect(document.querySelector('.career-history-status')).toHaveTextContent('Some resume details differ from your saved edits')
    fireEvent.click(screen.getByRole('button', { name: 'Review roles from latest resume' }))
    expect(review).toHaveAttribute('open')
    expect(review.scrollIntoView).toHaveBeenCalled()
    expect([...review.querySelectorAll('.cp-review-history strong')].map(row => row.textContent)).toEqual([
      'AI Intern', 'AI Developer', 'AI Intern', 'AI Developer',
    ])
    expect([...review.querySelectorAll('.cp-review-history small')].map(row => row.textContent)).toEqual([
      'Jan 2026 - Jul 2026', '2026-09-01 — End not specified',
      'Jan 2026 - Jul 2026', 'Sep 2026 - Present',
    ])
    expect(reviewRequest).not.toHaveBeenCalled()
  })
  it('recovers from polling failure and stops loading on terminal failure', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(queued)
    await mount()
    vi.mocked(api.resumeStatus).mockRejectedValue(new Error('Failed to fetch'))
    await act(() => vi.advanceTimersByTimeAsync(3000))
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
    await upload()
    expect(screen.queryByRole('button', { name: 'Career Settings' })).not.toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Upload failed')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
  it('times out a stalled status request and resumes polling instead of getting stuck', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(queued)
    await mount()
    vi.mocked(api.resumeStatus).mockImplementation(signal => new Promise((_, reject) => {
      signal?.addEventListener('abort', () => reject(new Error('Request timed out')))
    }))
    await act(() => vi.advanceTimersByTimeAsync(13_000))
    expect(screen.getByRole('status')).toHaveTextContent('Unable to check')
    vi.mocked(api.candidateProfile).mockResolvedValue(completed)
    vi.mocked(api.resumeStatus).mockResolvedValue({ resume: completed.latest_resume, worker_available: true })
    await act(() => vi.advanceTimersByTimeAsync(6000))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
  })
  it('polls only small status responses with backoff and cancels when unmounted', async () => {
    vi.mocked(api.candidateProfile).mockResolvedValue(queued)
    vi.mocked(api.resumeStatus).mockResolvedValue({ resume, worker_available: true })
    await mount()
    await act(() => vi.advanceTimersByTimeAsync(750))
    expect(api.resumeStatus).not.toHaveBeenCalled()
    await act(() => vi.advanceTimersByTimeAsync(2250))
    expect(api.resumeStatus).toHaveBeenCalledTimes(1)
    await act(() => vi.advanceTimersByTimeAsync(4500))
    expect(api.resumeStatus).toHaveBeenCalledTimes(2)
    expect(api.candidateProfile).toHaveBeenCalledTimes(1)
    cleanup()
    await act(() => vi.advanceTimersByTimeAsync(30000))
    expect(api.resumeStatus).toHaveBeenCalledTimes(2)
  })
})

it.each([false, true])('uses static reflection prompts without preference writes (replacement=%s)', async replacement => {
  vi.mocked(api.candidateProfile).mockResolvedValue(replacement ? completed : profile)
  vi.spyOn(api, 'uploadResume').mockResolvedValue(queued)
  const patch = vi.spyOn(api, 'updateCandidate')
  await mount(); await upload()
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(screen.getByText("We're turning your experience into a clearer picture of your career.")).toBeVisible()
  for (const text of ['Harder problems', 'More ownership', 'Exceptional people', 'Compensation']) {
    const chip = screen.getByText(text)
    expect(chip.tagName).toBe('LI')
    expect(chip).not.toHaveAttribute('tabindex')
    fireEvent.click(chip)
  }
  expect(patch).not.toHaveBeenCalled()
  expect(api.uploadResume).toHaveBeenCalledWith(file, undefined)
  vi.mocked(api.candidateProfile).mockResolvedValue(completed)
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
  expect(screen.queryByRole('progressbar')).toBeNull()
})

it('keeps polling a long-running job while pausing its animation and offering a status check', async () => {
  vi.mocked(api.candidateProfile).mockResolvedValue(queued)
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume, worker_available:true })
  await mount()
  await act(() => vi.advanceTimersByTimeAsync(61_000))
  expect(document.querySelector('.cp-processing-bar')).toHaveClass('is-paused')
  expect(screen.getByRole('button', { name:'Check status again' })).toBeVisible()
  const calls = vi.mocked(api.resumeStatus).mock.calls.length
  await act(() => vi.advanceTimersByTimeAsync(16_000))
  expect(vi.mocked(api.resumeStatus).mock.calls.length).toBeGreaterThan(calls)
  vi.mocked(api.candidateProfile).mockResolvedValue(completed)
  await act(async () => { fireEvent.click(screen.getByRole('button', { name:'Check status again' })) })
  expect(screen.queryByRole('progressbar')).toBeNull()
})

it('pauses polling in a hidden tab and checks immediately when it becomes active', async () => {
  vi.mocked(api.candidateProfile).mockResolvedValue(queued)
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume, worker_available: true })
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  await mount()
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(api.resumeStatus).toHaveBeenCalledTimes(1)
  hidden.mockReturnValue(true)
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  await act(() => vi.advanceTimersByTimeAsync(60000))
  expect(api.resumeStatus).toHaveBeenCalledTimes(1)
  hidden.mockReturnValue(false)
  vi.mocked(api.candidateProfile).mockResolvedValue(completed)
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume: completed.latest_resume, worker_available: true })
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(screen.queryByRole('progressbar')).toBeNull()
  expect(screen.getByRole('heading', { name: "Here's how we understand you." })).toBeVisible()
})

it('recovers a newer upload after refresh using the latest server resume, not a cached job ID', async () => {
  vi.mocked(api.candidateProfile).mockResolvedValue(queued)
  const newResume = { ...resume, id: 2, version: 2 }
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume: newResume, worker_available: true })
  await mount()
  vi.mocked(api.candidateProfile).mockResolvedValue({ ...queued, latest_resume: newResume })
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(screen.getByRole('progressbar')).toBeVisible()
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume: { ...newResume, processing_status: 'completed' }, worker_available: true })
  vi.mocked(api.candidateProfile).mockResolvedValue({ ...completed, latest_resume: { ...newResume, processing_status: 'completed' } })
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(screen.queryByRole('progressbar')).toBeNull()
})

it('a manual check retains the truthful worker delay and cannot create another upload', async () => {
  vi.mocked(api.candidateProfile).mockResolvedValue(queued)
  vi.mocked(api.resumeStatus).mockResolvedValue({ resume, worker_available: false })
  const uploadRequest = vi.spyOn(api, 'uploadResume')
  await mount()
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(screen.getByRole('status')).toHaveTextContent('temporarily delayed')
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Check status again' })) })
  expect(screen.getByRole('status')).toHaveTextContent('temporarily delayed')
  expect(uploadRequest).not.toHaveBeenCalled()
})
