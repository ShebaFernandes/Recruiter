import type { Candidate } from './types'

export function applicationProfileReady(profile: Candidate) {
  return profile.profile_status === 'submitted' && profile.can_submit &&
    profile.latest_resume?.processing_status === 'completed' &&
    profile.latest_resume.scan_status === 'clean' &&
    !profile.resume_identity_warning && !profile.resume_review
}
