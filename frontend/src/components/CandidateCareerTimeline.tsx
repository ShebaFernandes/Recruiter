import { useState } from 'react'
import type { CareerRolePatch, EmploymentExtraction, WorkExperience } from '../types'
import CareerJourney from './CareerJourney'
import CareerRoleEditor from './CareerRoleEditor'
import EmploymentHistoryStatus from './EmploymentHistoryStatus'
import { roleMissingDetails } from './careerRoleDates'

export default function CandidateCareerTimeline({ items, edit, saveRole, busy = false, reviewLatestResume, retryProcessing, extraction, identityWarning }: { items: WorkExperience[]; edit?: () => void; saveRole?: (id: number, patch: CareerRolePatch) => Promise<boolean>; busy?: boolean; reviewLatestResume?: () => void; retryProcessing?: () => void; extraction?: EmploymentExtraction | null; identityWarning?: string | null }) {
  const hasTimeline = items.length > 0
  const incomplete = items.filter(item => item.id != null && roleMissingDetails(item).length > 0)
  const datesOnly = incomplete.every(item => roleMissingDetails(item).every(detail => detail.startsWith('start') || detail.startsWith('end')))
  const missingLabel = `${incomplete.length} ${incomplete.length === 1 ? 'role needs' : 'roles need'} a ${datesOnly ? 'date' : 'detail'} check`
  const [editingRole, setEditingRole] = useState<WorkExperience | null>(null)
  const [focusField, setFocusField] = useState<string>()
  const [saved, setSaved] = useState(false)
  const openRole = (item: WorkExperience, fromPrompt = false) => {
    const missing = fromPrompt ? roleMissingDetails(item)[0] : ''
    setFocusField(missing === 'employer' ? 'company' : missing === 'job title' ? 'role' : missing?.startsWith('start') ? 'start' : missing?.startsWith('end') ? 'end' : 'company')
    setEditingRole(item)
    setSaved(false)
  }
  return <section className="cp-career" aria-labelledby="candidate-career-heading">
    <div className="cp-career-heading"><div><h3 id="candidate-career-heading">Your career journey</h3><p>Tap or hover over a marker to view your role.</p></div></div>
    <CareerJourney items={items} extraction={extraction} identityWarning={identityWarning} onEditRole={saveRole ? item => openRole(item) : undefined} showStatus={false} profilePresentation presentAtEnd candidateMilestones />
    <div className="cp-career-summary">
      {hasTimeline && <span>{items.length} saved {items.length === 1 ? 'role' : 'roles'} · Tap a marker for details</span>}
      <EmploymentHistoryStatus items={items} extraction={extraction} identityWarning={identityWarning} />
      {extraction?.status === 'review_required' && !hasTimeline && retryProcessing
        ? <button type="button" onClick={retryProcessing}>Retry reading resume</button>
        : extraction?.profile_state === 'pending_candidate_review' && reviewLatestResume
        ? <button type="button" onClick={reviewLatestResume}>Check saved edit</button>
        : !hasTimeline && edit && extraction?.status !== 'processing' && !identityWarning
        ? <button type="button" onClick={edit}>Add a role</button> : null}
    </div>
    {saveRole && incomplete.length > 0 && !editingRole && <div className="cp-career-complete"><span>{missingLabel}</span><button type="button" onClick={() => openRole(incomplete[0], true)}>{datesOnly ? 'Fix dates' : 'Fix details'}</button></div>}
    {editingRole?.id != null && saveRole && <CareerRoleEditor key={editingRole.id} item={editingRole} busy={busy} focusField={focusField} cancel={() => setEditingRole(null)} save={async patch => { const okay = await saveRole(editingRole.id!, patch); if (okay) { setEditingRole(null); setSaved(true) } return okay }} />}
    {saved && <p className="cp-career-saved" role="status">Career Journey updated. Your changes are saved.</p>}
  </section>
}
