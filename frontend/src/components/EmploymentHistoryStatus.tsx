import type { EmploymentExtraction, WorkExperience } from '../types'

/** Completion, candidate confirmation and latest-resume evidence are different facts. */
export default function EmploymentHistoryStatus({ items, extraction }: { items: WorkExperience[]; extraction?: EmploymentExtraction | null }) {
  const verified = extraction?.verified_role_ids?.length || 0
  let message: string
  if (extraction?.status === 'processing') message = 'The latest resume is still processing. Previously saved history has not yet been verified against this upload.'
  else if (extraction?.status === 'review_required' && extraction.reason_code !== 'no_resume') message = "We couldn't verify employment history in the latest resume. Review is needed; this does not confirm that you have no employment history." + (items.length ? " Saved roles remain on the timeline with review-needed markers." : " No saved employment roles are available to display.")
  else if (extraction?.status === 'confirmed_no_employment') message = 'No employment history declared in the latest resume. This is a resume statement; it does not erase previously saved records. Projects and education remain separate.'
  else if (verified) message = `${verified} saved ${verified === 1 ? 'role verified' : 'roles verified'} against the latest resume’s evidence${extraction?.source === 'rules' ? ' by ENTER’s local parser, not Gemini' : ''}.${extraction?.profile_state === 'pending_candidate_review' ? ' Additional resume changes are awaiting your review.' : ''}`
  else if (extraction?.profile_state === 'pending_candidate_review' && extraction.accepted_role_count > 0) message = 'Some resume details differ from your saved edits. Your Career Journey remains available; review the changes if you want to update them.'
  else if (extraction?.profile_state === 'pending_candidate_review') message = 'The latest resume contains changes awaiting your review. Hollow markers identify saved roles not verified against that upload.'
  else if (extraction?.resume_id != null && extraction.accepted_role_count > 0) message = 'The latest resume contains accepted employment evidence, but it does not match the saved roles. Saved roles remain visible with review-needed markers.'
  else if (items.length && items.every(item => item.confidence_status === 'candidate_confirmed') && (!extraction || extraction.reason_code === 'no_resume')) message = 'Employment history confirmed or manually edited by the candidate. It has not been verified against a latest resume.'
  else if (items.length) message = 'Saved employment history is shown with review-needed markers. Verification against the latest resume is not available.'
  else message = 'No verified employment history is available yet. An empty timeline does not confirm no employment.'
  return <p className={`career-history-status ${extraction?.stale_profile_preserved || extraction?.status === 'review_required' ? 'needs-review' : ''}`} role="status">{message}</p>
}
