import type { EmploymentExtraction, WorkExperience } from '../types'

/** Completion, candidate confirmation and latest-resume evidence are different facts. */
export default function EmploymentHistoryStatus({ items, extraction, identityWarning }: { items: WorkExperience[]; extraction?: EmploymentExtraction | null; identityWarning?: string | null }) {
  let message: string
  if (identityWarning === 'identity_unverified') message = 'Resume ownership needs confirmation.'
  else if (identityWarning === 'identity_mismatch') message = 'This resume may belong to someone else.'
  else if (extraction?.status === 'processing') message = 'Reading your latest resume.'
  else if (extraction?.status === 'review_required' && items.length) message = 'Latest resume could not be fully read; saved roles remain visible.'
  else if (extraction?.status === 'confirmed_no_employment' && items.length) message = 'Latest resume lists no jobs; saved roles remain visible.'
  else if (extraction?.profile_state === 'pending_candidate_review') message = 'A saved edit differs from the latest resume.'
  else if (items.length) return null
  else if (extraction?.status === 'confirmed_no_employment') message = 'No jobs were listed in this resume.'
  else if (extraction?.status === 'review_required' || ((extraction?.status === 'verified_ai' || extraction?.status === 'verified_fallback') && extraction.accepted_role_count === 0)) message = 'We could not verify work history from this resume.'
  else message = 'No roles saved yet.'
  return <p className={`career-history-status ${items.length || identityWarning || extraction?.status === 'review_required' ? 'needs-review' : ''}`} role="status">{message}</p>
}
