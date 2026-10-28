import type { EmploymentExtraction, WorkExperience } from '../types'

/** Completion, candidate confirmation and latest-resume evidence are different facts. */
export default function EmploymentHistoryStatus({ items, extraction, identityWarning }: { items: WorkExperience[]; extraction?: EmploymentExtraction | null; identityWarning?: string | null }) {
  let message: string
  if (identityWarning === 'identity_unverified') message = 'We could not verify that the latest resume belongs to your account. Earlier saved history remains visible; confirm ownership of that file to retry extraction.'
  else if (identityWarning === 'identity_mismatch') message = 'The latest resume appears to belong to someone else. Saved history remains visible; upload your own resume to continue.'
  else if (extraction?.status === 'processing') message = 'Your latest resume is processing. Your saved Career Journey remains available.'
  else if (extraction?.status === 'review_required' && items.length) message = 'The latest resume extraction is incomplete. Earlier saved roles remain visible and are not verified against this upload.'
  else if (extraction?.status === 'confirmed_no_employment' && items.length) message = 'The latest resume declares no employment. Earlier saved history remains visible until reconciliation is complete.'
  else if (extraction?.profile_state === 'pending_candidate_review') message = 'Some resume details differ from your saved edits. Your Career Journey remains available.'
  else if (items.length && extraction?.unverified_role_ids?.length) message = 'Some saved roles are not supported by the latest resume. They remain visible as older history.'
  else if (items.length) return null
  else if (extraction?.status === 'confirmed_no_employment') message = 'No employment history was declared in this resume.'
  else if (extraction?.status === 'review_required' || ((extraction?.status === 'verified_ai' || extraction?.status === 'verified_fallback') && extraction.accepted_role_count === 0)) message = 'We could not verify employment history from this resume. It may still contain jobs; you can try reading the saved file again or add your history manually.'
  else message = 'No employment history is saved yet.'
  return <p className={`career-history-status ${items.length || identityWarning || extraction?.status === 'review_required' ? 'needs-review' : ''}`} role="status">{message}</p>
}
