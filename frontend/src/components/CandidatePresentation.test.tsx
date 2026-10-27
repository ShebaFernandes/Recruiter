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
    ['processing', 'clean', 'Processing — extracting and validating your experience.'],
  ] as const)('presents the actual %s / %s state', (processing_status, scan_status, status) => {
    const { container } = render(<CandidateProcessing {...props()} resume={{ ...resume, processing_status, scan_status }} />)
    expect(screen.getByRole('heading', { name: "While we get to know you…" })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent(status)
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
    expect(screen.getByText(resume.original_name)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Retry processing' })).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d+%/)
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
  it('keeps the actual status stable and exits immediately on completion', () => {
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const { container, rerender } = render(<CandidateProcessing {...props()} />)
    act(() => vi.advanceTimersByTime(15000))
    expect(screen.getByRole('status')).toHaveTextContent('Queued')
    expect(container.querySelector('.cp-processing-message')).toBeNull()
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
    expect(container.querySelector('.cp-processing-message')).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Queued')
    rerender(<CandidateProcessing {...props()} error="Status unavailable" refresh={refresh} />)
    expect(screen.getByRole('status')).toHaveTextContent('Unable to check')
    fireEvent.click(screen.getByRole('button', { name: 'Check status again' }))
    expect(refresh).toHaveBeenCalledOnce()
  })
})

it('shows only real state changes, pauses an overdue animation and never claims completion', () => {
  vi.useFakeTimers()
  const refresh = vi.fn()
  const { container, rerender } = render(<CandidateProcessing {...props()} refresh={refresh} />)
  act(() => vi.advanceTimersByTime(60_000))
  expect(container.querySelector('.cp-processing-bar')).toHaveClass('is-paused')
  expect(screen.getByRole('status')).toHaveTextContent('taking longer than expected')
  fireEvent.click(screen.getByRole('button', { name:'Check status again' }))
  expect(refresh).toHaveBeenCalledOnce()
  rerender(<CandidateProcessing {...props()} refresh={refresh} resume={{ ...resume, processing_status:'processing', scan_status:'scanning' }} />)
  act(() => vi.advanceTimersByTime(0))
  expect(screen.getByRole('status')).toHaveTextContent('Scanning')
  expect(container.querySelector('.cp-processing-bar')).not.toHaveClass('is-paused')
  expect(screen.queryByText('Your profile is ready')).toBeNull()
})

it.each(['extracting', 'validating'] as const)('shows the backend %s phase without claiming success', processing_stage => {
  render(<CandidateProcessing {...props()} resume={{ ...resume, processing_status: 'processing', scan_status: 'clean', processing_stage }} />)
  expect(screen.getByRole('status')).toHaveTextContent(processing_stage === 'extracting' ? 'Extracting' : 'Validating')
  expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  expect(screen.queryByText('Your profile is ready')).toBeNull()
})
