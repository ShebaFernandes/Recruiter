import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react'
import { ChevronRight, FileText, FolderPlus, Plus, Search, UserRound, X } from 'lucide-react'
import type { Notification, Project, ProjectDetail, Search as SavedSearch } from '../types'

function countLabel(count: number, singular: string, plural: string) { return `${count} ${count === 1 ? singular : plural}` }

export function WorkspaceTime({ value }: { value: string }) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return <span>Date unavailable</span>
  const label = date.toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
  })
  return <time dateTime={value} title={label}>{label}</time>
}

export function ProjectWorkspace({ detail, openCandidate, removeCandidate, openSearch, startSearch, stageLabel, error }: {
  detail: ProjectDetail; openCandidate: (id: number) => void; removeCandidate: (id: number) => void
  openSearch: (search: SavedSearch) => void; startSearch: () => void; stageLabel: (value: string) => string; error: string
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [detail.project.id])
  return <div className="project-workspace workspace-ui">
    <div className="project-workspace-head"><div><span>PROJECT</span><h1 ref={heading} tabIndex={-1}>{detail.project.name}</h1><p>{detail.project.description || 'A focused shortlist for this hiring effort.'}</p></div><button className="primary" onClick={startSearch}><Search size={16} /> Start a search</button></div>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="project-stats"><div><b>{detail.project.candidate_count}</b><span>{detail.project.candidate_count === 1 ? 'Candidate' : 'Candidates'}</span></div><div><b>{detail.project.search_count}</b><span>{detail.project.search_count === 1 ? 'Search' : 'Searches'}</span></div></div>
    <section aria-labelledby="project-candidates-heading"><div className="project-section-head"><div><span>SHORTLIST</span><h2 id="project-candidates-heading">Saved candidates</h2></div></div>
      {detail.candidates.length ? <div className="project-candidates">{detail.candidates.map(({ id, candidate }) => <article key={id}>
        <div className="avatar" aria-hidden="true">{candidate.full_name.split(' ').map(value => value[0]).join('').slice(0, 2)}</div>
        <div className="workspace-candidate-info"><b>{candidate.full_name}</b><span>{candidate.headline}{candidate.current_company ? ` at ${candidate.current_company}` : ''}</span><small>{[candidate.location, `${candidate.total_experience} years`].filter(Boolean).join(' · ')}</small></div>
        <span className={`workspace-stage ${['non_relevant', 'rejected'].includes(candidate.stage) ? 'stage-closed' : candidate.stage ? 'stage-active' : ''}`} aria-label={`Hiring stage: ${candidate.stage ? stageLabel(candidate.stage) : 'Not staged'}`}>{candidate.stage ? stageLabel(candidate.stage) : 'Not staged'}</span>
        <button className="workspace-view-profile" onClick={() => openCandidate(candidate.id)}>View profile</button>
        <button className="remove-project-candidate" onClick={() => removeCandidate(candidate.id)} aria-label={`Remove ${candidate.full_name} from project`} title="Remove from project"><X size={16} /></button>
      </article>)}</div> : <div className="project-empty"><FolderPlus /><h3>No candidates saved yet</h3><p>Run a search in this project, then save strong matches from a candidate profile.</p></div>}
    </section>
    <section aria-labelledby="project-searches-heading"><div className="project-section-head"><div><span>SEARCH HISTORY</span><h2 id="project-searches-heading">Searches in this project</h2></div></div>
      {detail.searches.length ? <div className="project-searches">{detail.searches.map(item => <button key={item.id} onClick={() => openSearch(item)}><span>{item.query}</span><small>{item.state === 'complete' ? 'View results' : 'Continue conversation'}<WorkspaceTime value={item.created_at} /></small><ChevronRight size={16} aria-hidden="true" /></button>)}</div> : <p className="muted">No searches have been saved to this project.</p>}
    </section>
  </div>
}

export type WorkspacePanelName = 'recents' | 'projects' | 'updates'
const panelTitles = { recents: 'Recent searches', projects: 'Projects', updates: 'Candidate updates' }

export function WorkspacePanel({ panel, close, recents, projects, notifications, selectedProject, newProjectName, setNewProjectName, createProject, busy, chooseRecent, openProject, openNotification, error }: {
  panel: WorkspacePanelName; close: () => void; recents: SavedSearch[]; projects: Project[]; notifications: Notification[]
  selectedProject: number | null; newProjectName: string; setNewProjectName: (name: string) => void
  createProject: (event: FormEvent) => void; busy: boolean; chooseRecent: (search: SavedSearch) => void
  openProject: (id: number) => void; openNotification: (item: Notification) => void; error: string
}) {
  const panelRef = useRef<HTMLElement>(null)
  useEffect(() => { panelRef.current?.querySelector<HTMLButtonElement>('button')?.focus() }, [panel])
  function dismiss() {
    close()
    document.querySelector<HTMLButtonElement>(`.recruiter-rail [aria-label="${panelTitles[panel]}"]`)?.focus()
  }
  function viewUpdate(item: Notification) {
    // The panel closes when the profile opens. Give its dialog a persistent
    // return-focus target rather than the soon-to-be-unmounted update button.
    document.querySelector<HTMLButtonElement>('.recruiter-rail [aria-label="Candidate updates"]')?.focus()
    openNotification(item)
  }
  function handleKeys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') { event.preventDefault(); dismiss(); return }
    if (event.key !== 'Tab' || !window.matchMedia('(max-width: 900px)').matches || getComputedStyle(event.currentTarget).position !== 'fixed') return
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
    const first = items[0], last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
  return <aside ref={panelRef} className="workspace-sidepanel workspace-ui" aria-label={panelTitles[panel]} onKeyDown={handleKeys}>
    <header><div><span>WORKSPACE</span><h2>{panelTitles[panel]}</h2></div><button onClick={dismiss} aria-label="Close workspace panel" title="Close panel"><X /></button></header>
    <div className="workspace-panel-body">
      {error && <p className="error" role="alert">{error}</p>}
      {panel === 'recents' && <nav className="workspace-list" aria-label="Saved recent searches">{recents.length ? recents.map(item => <button key={item.id} onClick={() => chooseRecent(item)}><span>{item.query}</span><small>{item.state === 'complete' ? 'View results' : 'Continue conversation'}<WorkspaceTime value={item.created_at} /></small><ChevronRight className="workspace-row-arrow" size={16} aria-hidden="true" /></button>) : <p>No searches yet. Your completed and in-progress searches will appear here.</p>}</nav>}
      {panel === 'projects' && <><form className="project-create" onSubmit={createProject}><label>New project name<input aria-label="New project name" value={newProjectName} onChange={event => setNewProjectName(event.target.value)} placeholder="e.g. Backend hiring" /></label><button className="primary" aria-label="Create project" disabled={busy || !newProjectName.trim()}><Plus size={15} /> Create</button></form><nav className="workspace-list" aria-label="Saved projects">{projects.length ? projects.map(item => <button className={selectedProject === item.id ? 'active' : ''} aria-current={selectedProject === item.id ? 'true' : undefined} key={item.id} onClick={() => openProject(item.id)}><span>{item.name}</span><small>{countLabel(item.candidate_count, 'candidate', 'candidates')} · {countLabel(item.search_count, 'search', 'searches')}</small><ChevronRight className="workspace-row-arrow" size={16} aria-hidden="true" /></button>) : <p>No projects yet. Create one to keep candidates and searches together.</p>}</nav></>}
      {panel === 'updates' && <nav className="workspace-list update-list" aria-label="Candidate update history">{notifications.length ? notifications.map(item => <button className={item.is_read ? 'read' : ''} key={item.id} onClick={() => viewUpdate(item)}>
        <span className="workspace-update-type">{item.change_type === 'resume' ? <FileText size={15} aria-hidden="true" /> : <UserRound size={15} aria-hidden="true" />}{item.change_type === 'resume' ? 'Resume' : 'Profile'}<em>{item.is_read ? 'Seen' : 'New'}</em></span>
        <span>{item.candidate_name}</span><b>{item.message}</b><small><WorkspaceTime value={item.created_at} /></small><ChevronRight className="workspace-row-arrow" size={16} aria-hidden="true" />
      </button>) : <p>No candidate updates yet.</p>}</nav>}
    </div>
  </aside>
}
