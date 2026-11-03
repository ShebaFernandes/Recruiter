import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type { Candidate } from '../types'
import { api } from '../api'
import OpportunityApplication from './OpportunityApplication'
import { applicationProfileReady } from '../opportunityApplication'

const { reviewed } = vi.hoisted(() => ({ reviewed: { value: null as Candidate | null } }))
vi.mock('./CandidateExperience', () => ({ default: ({ opportunity }: { opportunity: { onContinue: (p: Candidate) => void } }) => <button onClick={() => opportunity.onContinue(reviewed.value!)}>Review application</button> }))
vi.mock('./PlatformBackground', () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
const ready = { full_name: 'Alex Example', location: 'Bengaluru', profile_status: 'submitted', can_submit: true, profile_updated_at: 'v1', latest_resume: { id: 9, original_name: 'alex.pdf', processing_status: 'completed', scan_status: 'clean' } } as Candidate
const role = { id: 'backend-engineer', title: 'Backend Engineer' }
beforeEach(() => { vi.spyOn(window, 'scrollTo').mockImplementation(() => {}) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear() })
function setup(profile = ready) {
  reviewed.value = profile
  vi.spyOn(api, 'candidateProfile').mockResolvedValue(profile)
  return render(<OpportunityApplication role={role} onBack={vi.fn()} />)
}
async function confirm() {
  fireEvent.click(await screen.findByRole('button', { name: 'Use current CV' }))
  fireEvent.click(screen.getByRole('button', { name: 'Review application' }))
  fireEvent.click(screen.getByRole('checkbox'))
}
describe('opportunity application', () => {
  it('requires CV selection, review and explicit confirmation before submitting the remembered role', async () => {
    sessionStorage.setItem('enter-opportunity-intent', role.id)
    const submit = vi.spyOn(api, 'applyOpportunity').mockResolvedValue({ detail: 'Your application has been received.' })
    setup(); await confirm()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Interested in this role.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit application' }))
    expect(await screen.findByText('Your application has been received.')).toBeVisible()
    expect(submit).toHaveBeenCalledWith(role.id, 'Interested in this role.')
    expect(sessionStorage.getItem('enter-opportunity-intent')).toBeNull()
  })
  it('uploads a new CV through the existing API before opening profile review', async () => {
    const upload = vi.spyOn(api, 'uploadResume').mockResolvedValue(ready)
    setup({ ...ready, latest_resume: null, profile_status: 'draft' })
    const input = await screen.findByLabelText('Upload your CV')
    fireEvent.change(input, { target: { files: [new File(['cv'], 'alex.pdf', { type: 'application/pdf' })] } })
    expect(await screen.findByRole('button', { name: 'Review application' })).toBeVisible()
    expect(upload).toHaveBeenCalledTimes(1)
  })
  it('rejects invalid files and retains the upload screen on API errors', async () => {
    const upload = vi.spyOn(api, 'uploadResume').mockRejectedValue(new Error('Scanner unavailable. Please retry.'))
    setup({ ...ready, latest_resume: null })
    const input = await screen.findByLabelText('Upload your CV')
    fireEvent.change(input, { target: { files: [new File(['x'], 'bad.exe')] } })
    expect(upload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a PDF or DOCX')
    fireEvent.change(input, { target: { files: [new File(['cv'], 'alex.pdf')] } })
    expect(await screen.findByText('Scanner unavailable. Please retry.')).toBeVisible()
  })
  it('requires another review when the CV changes before submission', async () => {
    const submit = vi.spyOn(api, 'applyOpportunity')
    setup(); await confirm()
    vi.mocked(api.candidateProfile).mockResolvedValue({ ...ready, profile_updated_at: 'v2' })
    fireEvent.click(screen.getByRole('button', { name: 'Submit application' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Please review it again')
    expect(submit).not.toHaveBeenCalled()
  })
  it('keeps the application retryable after a submission error', async () => {
    vi.spyOn(api, 'applyOpportunity').mockRejectedValue(new Error('Please try again.'))
    setup(); await confirm()
    fireEvent.click(screen.getByRole('button', { name: 'Submit application' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Please try again.'))
    expect(screen.getByRole('button', { name: 'Submit application' })).toBeEnabled()
  })
  it('blocks draft profiles, pending processing, unsafe scans and unresolved ownership or profile reviews', () => {
    expect(applicationProfileReady(ready)).toBe(true)
    for (const patch of [{ latest_resume: null }, { profile_status: 'draft' }, { can_submit: false }, { resume_identity_warning: { code: 'identity_unverified' } }, { resume_review: {} }, { latest_resume: { ...ready.latest_resume, processing_status: 'processing' } }, { latest_resume: { ...ready.latest_resume, scan_status: 'infected' } }]) {
      expect(applicationProfileReady({ ...ready, ...patch } as Candidate)).toBeFalsy()
    }
  })
})
