import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProjectWorkspace, WorkspacePanel, WorkspaceTime } from './RecruiterWorkspace'
import type { Candidate, ProjectDetail, Search } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const savedSearch = { id: 3, query: 'Backend engineer, remote', state: 'complete', created_at: '2026-10-08T09:00:00Z' } as Search
const project = { id: 1, name: 'Platform hiring', description: '', candidate_count: 1, search_count: 1, created_at: '2026-10-08T09:00:00Z' }
const panelProps = () => ({ panel: 'projects' as const, close: vi.fn(), recents: [savedSearch], projects: [project], notifications: [], selectedProject: 1, newProjectName: '', setNewProjectName: vi.fn(), createProject: vi.fn(), busy: false, chooseRecent: vi.fn(), openProject: vi.fn(), openNotification: vi.fn(), error: '' })

describe('recruiter workspace presentation', () => {
  it('shows actual project counts and preserves project selection', () => {
    const props = panelProps()
    render(<WorkspacePanel {...props} />)
    expect(screen.getByRole('button', { name: 'Close workspace panel' })).toHaveFocus()
    const projectButton = screen.getByRole('button', { name: /Platform hiring/ })
    expect(projectButton).toHaveTextContent('1 candidate · 1 search')
    expect(projectButton).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('button', { name: 'Create project' })).toBeDisabled()
    fireEvent.click(projectButton)
    expect(props.openProject).toHaveBeenCalledWith(1)
  })
  it('keeps recent queries, real timestamps, and resume-conversation actions', () => {
    const props = panelProps()
    const { container } = render(<WorkspacePanel {...props} panel="recents" recents={[{ ...savedSearch, state: 'needs_clarification' }]} />)
    expect(container.querySelector('time')).toHaveAttribute('datetime', savedSearch.created_at)
    fireEvent.click(screen.getByRole('button', { name: /Continue conversation/ }))
    expect(props.chooseRecent).toHaveBeenCalledWith(expect.objectContaining({ id: 3 }))
  })
  it('distinguishes only supplied update types and preserves acknowledgement action', () => {
    const props = panelProps()
    const notifications = [
      { id: 4, candidate: 2, candidate_name: 'Maya Rao', change_type: 'resume' as const, message: 'Updated resume', is_read: false, created_at: savedSearch.created_at },
      { id: 5, candidate: 2, candidate_name: 'Maya Rao', change_type: 'profile' as const, message: 'Profile updated', is_read: true, created_at: savedSearch.created_at },
    ]
    render(<WorkspacePanel {...props} panel="updates" notifications={notifications} />)
    expect(screen.getByText('New')).toBeVisible()
    expect(screen.getByText('Seen')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: /Updated resume/ }))
    expect(props.openNotification).toHaveBeenCalledWith(notifications[0])
  })
  it('shows empty states without invented activity', () => {
    render(<WorkspacePanel {...panelProps()} panel="updates" />)
    expect(screen.getByText('No candidate updates yet.')).toBeVisible()
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })
  it('contains mobile keyboard focus and closes with Escape', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
    const props = panelProps()
    render(<WorkspacePanel {...props} />)
    screen.getByRole('complementary').style.position = 'fixed'
    fireEvent.keyDown(screen.getByRole('button', { name: 'Close workspace panel' }), { key: 'Tab', shiftKey: true })
    expect(screen.getByRole('button', { name: /Platform hiring/ })).toHaveFocus()
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(props.close).toHaveBeenCalledOnce()
  })
  it('shows persisted shortlist stages and keeps profile/removal actions', () => {
    const candidate = { id: 2, full_name: 'Maya Rao', headline: 'Engineer', current_company: 'Example', location: 'Pune', total_experience: '4', stage: 'shortlisted' } as Candidate
    const detail: ProjectDetail = { project, candidates: [{ id: 1, candidate, added_at: '' }], searches: [savedSearch] }
    const openCandidate = vi.fn(), removeCandidate = vi.fn()
    render(<ProjectWorkspace detail={detail} openCandidate={openCandidate} removeCandidate={removeCandidate} openSearch={vi.fn()} startSearch={vi.fn()} stageLabel={() => 'Shortlisted'} error="" />)
    expect(screen.getByLabelText('Hiring stage: Shortlisted')).toHaveClass('stage-active')
    expect(screen.getByRole('heading', { name: 'Platform hiring' })).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'View profile' }))
    expect(openCandidate).toHaveBeenCalledWith(2)
    fireEvent.click(screen.getByRole('button', { name: 'Remove Maya Rao from project' }))
    expect(removeCandidate).toHaveBeenCalledWith(2)
  })
  it('does not manufacture a date if the timestamp is unavailable', () => {
    render(<WorkspaceTime value="" />)
    expect(screen.getByText('Date unavailable')).toBeVisible()
  })
})
