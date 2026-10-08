import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import type { Resume } from '../types'
import ResumeAccess from './ResumeAccess'

vi.mock('../api', () => ({ api: { resumeDocument: vi.fn() } }))
const resume: Resume = {
  id: 1, original_name: 'resume.pdf', version: 1, uploaded_at: '',
  processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false,
  url: '/api/v1/resumes/1/download/',
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('authorized recruiter resume access', () => {
  it('does not offer access without an authorized URL or with an unprocessed file', () => {
    const { rerender } = render(<ResumeAccess resume={null} />)
    expect(screen.queryByText('View Resume')).not.toBeInTheDocument()
    rerender(<ResumeAccess resume={{ ...resume, url: null }} />)
    expect(screen.queryByText('View Resume')).not.toBeInTheDocument()
    rerender(<ResumeAccess resume={{ ...resume, scan_status: 'quarantined' }} />)
    expect(screen.queryByText('View Resume')).not.toBeInTheDocument()
  })
  it('provides a secure DOCX download and explains how to open it', () => {
    render(<ResumeAccess resume={{ ...resume, original_name: 'resume.docx' }} />)
    expect(screen.getByRole('link', { name: 'View Resume' })).toHaveAttribute('href', resume.url)
    expect(screen.getByRole('link', { name: 'View Resume' })).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText(/DOCX opens as a download/)).toBeVisible()
  })
  it('fetches PDF bytes through the authorized API and revokes the temporary preview on close', async () => {
    const tab = { opener: {}, document: { title: '', body: { textContent: '' } }, closed: false, location: { replace: vi.fn() }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    const create = vi.fn(() => 'blob:private-preview')
    const revoke = vi.fn()
    vi.stubGlobal('URL', class extends URL { static createObjectURL = create; static revokeObjectURL = revoke })
    vi.mocked(api.resumeDocument).mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }))
    const { unmount } = render(<ResumeAccess resume={resume} />)
    fireEvent.click(screen.getByRole('button', { name: 'View Resume' }))
    await waitFor(() => expect(tab.location.replace).toHaveBeenCalledWith('blob:private-preview'))
    expect(api.resumeDocument).toHaveBeenCalledWith(1)
    expect(tab.opener).toBeNull()
    unmount()
    expect(revoke).toHaveBeenCalledWith('blob:private-preview')
  })
  it('closes the preview tab on denied access and shows an error', async () => {
    const tab = { opener: {}, document: { title: '', body: { textContent: '' } }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    vi.mocked(api.resumeDocument).mockRejectedValue(new Error('Resume access is unavailable.'))
    render(<ResumeAccess resume={resume} />)
    fireEvent.click(screen.getByRole('button', { name: 'View Resume' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Resume access is unavailable.')
    expect(tab.close).toHaveBeenCalled()
  })
  it('offers recovery when the browser blocks the new tab', () => {
    vi.spyOn(window, 'open').mockReturnValue(null)
    render(<ResumeAccess resume={resume} />)
    fireEvent.click(screen.getByRole('button', { name: 'View Resume' }))
    expect(screen.getByRole('alert')).toHaveTextContent('blocked the preview')
    expect(screen.getByRole('link', { name: 'Download resume' })).toBeVisible()
  })
})
