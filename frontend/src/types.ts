export type User = { id: number; email: string; role: 'candidate' | 'recruiter'; full_name: string }
export type WorkExperience = {
  id?: number
  company: string
  role: string
  start_date: string | null
  end_date: string | null
  is_current?: boolean
  date_label?: string
  employment_type?: string
  location?: string
  description: string
  confidence_status?: 'supported' | 'partial' | 'candidate_confirmed'
  gap_reason: string
}
export type EmploymentExtraction = {
  resume_id?: number | null
  resume_processing_status?: Resume['processing_status'] | null
  verified_role_ids?: number[]
  candidate_confirmed_role_ids?: number[]
  unverified_role_ids?: number[]
  status: 'verified_ai' | 'verified_fallback' | 'confirmed_no_employment' | 'review_required' | 'processing'
  source: 'ai' | 'rules' | 'unknown'
  reason_code: string
  accepted_role_count: number
  saved_role_count: number
  profile_state: 'pending' | 'applied' | 'pending_candidate_review' | 'previous_history_preserved' | 'not_applied' | 'empty' | 'unchanged'
  stale_profile_preserved: boolean
}
export type Resume = {
  id: number
  original_name: string
  version: number
  uploaded_at: string
  processing_status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
  scan_status: 'quarantined' | 'scanning' | 'clean' | 'infected' | 'failed'
  processing_stage?: 'uploaded' | 'queued' | 'scanning' | 'extracting' | 'validating' | 'processing' | 'completed' | 'failed'
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
  career_preferences?: CareerPreferences
  build_lead_preference: number | null
  profile_photo_url: string | null
  available_resume?: Resume | null
  resume_identity_warning?: { resume_id: number; code: string } | null
  resume_review?: { resume_id: number; fields: Partial<Candidate>; original_name?: string } | null
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
  employment_extraction?: EmploymentExtraction | null
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
export type CareerPreferences = {
  portfolio_url?: string
  custom_motivators?: string[]
  custom_exclusions?: string[]
  motivators?: string[]
  exclusions?: string[]
  availability?: string
  preferred_locations?: string[]
  contact_preferences?: string[]
  strongest_skills?: string[]
  standout_signal?: string
  likely_directions?: string[]
}
export type DocumentPreview = { blocks: Array<
  { type: 'paragraph'; runs: { text: string; bold: boolean; italic: boolean }[] } |
  { type: 'table'; rows: string[][] }
> }
export type Search = {
  id: number
  project: number | null
  project_name: string
  query: string
  criteria: Record<string, string | number | boolean | null | string[]>
  state: 'needs_clarification' | 'complete'
  follow_up_question: string
  follow_up_options: string[]
  understanding_source: 'anthropic' | 'openai' | 'deterministic' | 'deterministic_fallback'
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
