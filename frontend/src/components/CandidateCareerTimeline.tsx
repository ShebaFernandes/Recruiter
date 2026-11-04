import { useState } from 'react'
import type { CareerRolePatch, EmploymentExtraction, WorkExperience } from '../types'
import CareerJourney from './CareerJourney'
import CareerRoleEditor from './CareerRoleEditor'
import { roleMissingDetails } from './careerRoleDates'

export default function CandidateCareerTimeline({ items, edit, saveRole, busy = false, reviewLatestResume, retryProcessing, extraction, identityWarning }: { items: WorkExperience[]; edit?: () => void; saveRole?: (id: number, patch: CareerRolePatch) => Promise<boolean>; busy?: boolean; identityWarning?: string | null; reviewLatestResume?: () => void; retryProcessing?: () => void; extraction?: EmploymentExtraction | null }) {
  const stale = extraction?.stale_profile_preserved
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
    <div className="cp-career-heading"><div><h3 id="candidate-career-heading">Your career journey</h3><p>{hasTimeline ? 'Employment dates to scale. Hover or tap a role for details.' : 'Latest resume verification and safely retained records.'}</p></div></div>
    <div className={stale ? 'cp-career-previous' : ''}><CareerJourney items={items} extraction={extraction} identityWarning={identityWarning} onEditRole={saveRole ? item => openRole(item) : undefined} profilePresentation presentAtEnd candidateMilestones /></div>
    {extraction?.status === 'review_required' && !items.length && retryProcessing
      ? <button type="button" onClick={retryProcessing}>Try reading this saved resume again (without AI)</button>
      : extraction?.profile_state === 'pending_candidate_review' && reviewLatestResume
      ? <button type="button" onClick={reviewLatestResume}>Review roles from latest resume</button>
      : !items.length && edit && <button type="button" onClick={edit}>Add employment history</button>}
    {saveRole && incomplete.length > 0 && !editingRole && <div className="cp-career-complete"><span>{missingLabel}</span><button type="button" onClick={() => openRole(incomplete[0], true)}>{datesOnly ? 'Fix dates' : 'Fix details'}</button></div>}
    {editingRole?.id != null && saveRole && <CareerRoleEditor key={editingRole.id} item={editingRole} busy={busy} focusField={focusField} cancel={() => setEditingRole(null)} save={async patch => { const okay = await saveRole(editingRole.id!, patch); if (okay) { setEditingRole(null); setSaved(true) } return okay }} />}
    {saved && <p className="cp-career-saved" role="status">Career Journey updated. Your changes are saved.</p>}
  </section>
}
