import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CandidateProcessing, CandidateWelcome } from './CandidatePresentation'
import type { Resume } from '../types'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
const resume: Resume = { id: 1, original_name: 'My resume.docx', version: 1, uploaded_at: '', processing_status: 'queued', scan_status: 'quarantined', processing_error: '', can_retry: false, url: null }
const props = () => ({ resume, uploading: false, retry: vi.fn(), upload: vi.fn(), error: '' })

describe('candidate presentation', () => {
  it('uses the approved exact welcome copy', () => {
    render(<CandidateWelcome />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Let's find work that feels great.")
    expect(screen.getByRole('paragraph')).toHaveTextContent('Join Leading Startups Building Their Teams with ENTER')
  })
  it.each([
    ['uploaded', 'quarantined', 'Uploaded — waiting to be queued.'],
    ['queued', 'quarantined', 'Queued — waiting for a resume worker.'],
    ['processing', 'scanning', 'Scanning — checking your file safely.'],
    ['processing', 'clean', 'Processing — preparing your profile.'],
  ] as const)('presents the actual %s / %s state', (processing_status, scan_status, status) => {
    const { container } = render(<CandidateProcessing {...props()} resume={{ ...resume, processing_status, scan_status }} />)
    expect(screen.getByRole('heading', { name: "We're doing the boring part." })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent(status)
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
    expect(screen.getByText(resume.original_name)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Retry processing' })).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d+%/)
    expect(screen.getByRole('list')).toHaveAccessibleName('Profile preparation activities, not completed stages')
  })
  it('keeps failure, retry and replacement actions connected to their callbacks', () => {
    const actions = props()
    render(<CandidateProcessing {...actions} resume={{ ...resume, processing_status: 'failed', can_retry: true, processing_error: 'We could not read this document.' }} />)
    expect(screen.getByText('We could not read this document.')).toBeVisible()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
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
  it('cycles all five descriptions without changing the backend status or delaying completion', () => {
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const { container, rerender } = render(<CandidateProcessing {...props()} />)
    for (const text of ['Reading your experience', 'Mapping your career journey', 'Identifying your strongest skills', "Understanding what you've built", 'Building your ENTER profile']) {
      expect(container.querySelector('.cp-processing-message')).toHaveTextContent(text)
      expect(screen.getByRole('status')).toHaveTextContent('Queued')
      act(() => vi.advanceTimersByTime(3000))
    }
    rerender(<CandidateProcessing {...props()} resume={{ ...resume, processing_status: 'completed' }} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Your profile is ready' })).toBeVisible()
  })
  it('does not cycle messages with reduced motion and offers recovery for polling errors', () => {
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const refresh = vi.fn()
    const { container, rerender } = render(<CandidateProcessing {...props()} />)
    act(() => vi.advanceTimersByTime(6000))
    expect(container.querySelector('.cp-processing-message')).toHaveTextContent('Reading your experience')
    rerender(<CandidateProcessing {...props()} error="Status unavailable" refresh={refresh} />)
    expect(screen.getByRole('status')).toHaveTextContent('Unable to check')
    fireEvent.click(screen.getByRole('button', { name: 'Check status again' }))
    expect(refresh).toHaveBeenCalledOnce()
  })
})
