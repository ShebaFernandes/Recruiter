import type { EmploymentExtraction, WorkExperience } from '../types'

/** Completion, candidate confirmation and latest-resume evidence are different facts. */
export default function EmploymentHistoryStatus({ items, extraction }: { items: WorkExperience[]; extraction?: EmploymentExtraction | null }) {
  let message: string
  if (extraction?.status === 'processing') message = 'Your latest resume is processing. Your saved Career Journey remains available.'
  else if (extraction?.profile_state === 'pending_candidate_review') message = 'Some resume details differ from your saved edits. Your Career Journey is ready; you can compare those changes if you wish.'
  else if (items.length) return null
  else if (extraction?.status === 'confirmed_no_employment') message = 'No employment history was declared in this resume.'
  else if (extraction?.status === 'review_required') message = 'We could not find supported employment history in this resume. You can add your history manually.'
  else message = 'No employment history is saved yet.'
  return <p className="career-history-status" role="status">{message}</p>
}
