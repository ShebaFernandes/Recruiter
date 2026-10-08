import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CandidateProcessing, CandidateWelcome } from './CandidatePresentation'
import type { Resume } from '../types'

afterEach(cleanup)
const resume: Resume = { id: 1, original_name: 'My resume.docx', version: 1, uploaded_at: '', processing_status: 'queued', scan_status: 'quarantined', processing_error: '', can_retry: false, url: null }
const props = () => ({ resume, uploading: false, retry: vi.fn(), upload: vi.fn(), error: '' })

describe('candidate presentation', () => {
  it('uses the approved exact welcome copy', () => {
    render(<CandidateWelcome />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Let's find work that feels great.")
    expect(screen.getByText('Join Leading Startups Building Their Teams with ENTER')).toBeVisible()
  })
  it.each([
    ['uploaded', 'quarantined', 'Your resume is uploaded'],
    ['queued', 'quarantined', 'Your resume is queued'],
    ['processing', 'scanning', 'Checking your resume…'],
    ['processing', 'clean', 'Reading your resume…'],
  ] as const)('presents the actual %s / %s state', (processing_status, scan_status, heading) => {
    const { container } = render(<CandidateProcessing {...props()} resume={{ ...resume, processing_status, scan_status }} />)
    expect(screen.getByRole('heading', { name: heading })).toBeVisible()
    expect(screen.getByText(resume.original_name)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Retry processing' })).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d+%/)
    expect(container.querySelector('[aria-live="polite"]')).toBeInTheDocument()
  })
  it('keeps failure, retry and replacement actions connected to their callbacks', () => {
    const actions = props()
    render(<CandidateProcessing {...actions} resume={{ ...resume, processing_status: 'failed', can_retry: true, processing_error: 'We could not read this document.' }} />)
    expect(screen.getByText('We could not read this document.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Retry processing' }))
    expect(actions.retry).toHaveBeenCalledOnce()
    const file = new File(['test fixture'], 'replacement.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Upload a replacement resume'), { target: { files: [file] } })
    expect(actions.upload).toHaveBeenCalledWith(file)
  })
  it('does not offer retry when the backend disallows it and exposes errors', () => {
    render(<CandidateProcessing {...props()} resume={{ ...resume, processing_status: 'failed' }} error="Please choose a different file." />)
    expect(screen.queryByRole('button', { name: 'Retry processing' })).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Please choose a different file.')
  })
  it('disables retry and replacement while an upload is pending', () => {
    render(<CandidateProcessing {...props()} uploading resume={{ ...resume, processing_status: 'failed', can_retry: true }} />)
    expect(screen.getByRole('button', { name: 'Queueing…' })).toBeDisabled()
    expect(screen.getByLabelText('Upload a replacement resume')).toBeDisabled()
  })
})
