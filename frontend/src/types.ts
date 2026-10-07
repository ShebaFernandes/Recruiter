export type User = { id: number; email: string; role: 'candidate' | 'recruiter'; full_name: string }
export type WorkExperience = {
  id?: number
  company: string
  role: string
  start_date: string
  end_date: string | null
  description: string
  gap_reason: string
}
export type Resume = {
  id: number
  original_name: string
  version: number
  uploaded_at: string
  processing_status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
  scan_status: 'quarantined' | 'scanning' | 'clean' | 'infected' | 'failed'
  processing_error: string
  can_retry: boolean
  url: string | null
}
export type MissingField = {
  field: string
  label: string
  category: 'required' | 'recommended' | 'optional'
  message: string
  prompt: string
  options?: Array<string | number>
}
export type ProfileCompletion = {
  percent: number
  remaining: number
  required_missing: number
  recommended_missing: number
}
export type Candidate = {
  id: number
  full_name: string
  headline: string
  current_company: string
  email: string
  phone: string
  location: string
  total_experience: string
  notice_period_days: number | null
  current_salary_lpa: string | null
  expected_salary_lpa: string | null
  employment_type: string
  linkedin_url: string
  github_url: string
  summary: string
  meaningful_work: string
  visibility: '' | 'approved_recruiters' | 'matching_roles' | 'not_looking'
  work_preferences: string[]
  skills: string[]
  education: string[]
  profile_status: 'draft' | 'submitted'
  email_verified_at: string | null
  submitted_at: string | null
  submission_consent_at: string | null
  submission_consent_version: string
  discovery_status: 'draft' | 'submitted' | 'not_looking'
  profile_updated_at: string
  work_experiences: WorkExperience[]
  latest_resume: Resume | null
  viewed: boolean
  stage: string
  resume_updated: boolean
  update_label: string
  missing_fields: MissingField[]
  profile_completion: ProfileCompletion
  submission_missing_fields: MissingField[]
  can_submit: boolean
}
export type Search = {
  id: number
  project: number | null
  project_name: string
  query: string
  criteria: Record<string, string | number | boolean | null | string[]>
  state: 'needs_clarification' | 'complete'
  follow_up_question: string
  follow_up_options: string[]
  understanding_source: 'openai' | 'deterministic' | 'deterministic_fallback'
  understanding_model: string
  created_at: string
}
export type SearchResult = { candidate: Candidate; match_score: number; match_reasons: string[] }
export type Project = {
  id: number
  name: string
  description: string
  candidate_count: number
  search_count: number
  created_at: string
}
export type ProjectMembership = { id: number; candidate: Candidate; added_at: string }
export type ProjectDetail = { project: Project; candidates: ProjectMembership[]; searches: Search[] }
export type Notification = {
  id: number
  candidate: number
  candidate_name: string
  change_type: 'resume' | 'profile'
  message: string
  is_read: boolean
  created_at: string
}
