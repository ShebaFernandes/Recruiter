import type { Candidate, Notification, Project, ProjectDetail, Search, SearchResult, User } from './types'

export type AuthPayload = { token?: string; user: User }
export type SignupResponse = AuthPayload | { detail: string; requires_email_verification: true; local_verification_url?: string }

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const auth = { save: (payload: AuthPayload) => void payload, clear: () => undefined }

export class ApiError extends Error {
  status: number
  code: string
  constructor(message: string, status: number, code = '') { super(message); this.status = status; this.code = code }
}

let csrfToken = ''

async function ensureCsrfToken() {
  if (csrfToken) return csrfToken
  let response: Response
  try {
    response = await fetch(`${API_URL}/auth/csrf/`, { credentials: 'include' })
  } catch {
    throw new ApiError('We can’t reach Enter right now. Check your connection and try again.', 0, 'connection')
  }
  if (!response.ok) throw new ApiError('Enter is temporarily unavailable. Please try again.', response.status, 'server')
  const body = await response.json() as { csrfToken: string }
  csrfToken = body.csrfToken
  return csrfToken
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const method = (options.method || 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRFToken', await ensureCsrfToken())
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: 'include' })
  } catch {
    throw new ApiError('We can’t reach Enter right now. Check your connection and try again.', 0, 'connection')
  }
  if (!response.ok) {
    let message = 'The request could not be completed.'
    let code = ''
    try {
      const body = await response.json()
      message = body.detail || Object.values(body).flat().join(' ') || message
      code = body.code || ''
    } catch { /* preserve fallback */ }
    if (response.status === 401) {
      message = 'Your session has expired. Please sign in again.'
      window.dispatchEvent(new CustomEvent('enter-auth-expired'))
    }
    else if (response.status === 429 && !code) message = 'Too many requests. Please wait a moment and try again.'
    else if (response.status >= 500 && !code) message = 'Enter is temporarily unavailable. Your information was not lost. Please try again.'
    throw new ApiError(message, response.status, code || (response.status === 401 ? 'auth_expired' : ''))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  me: () => request<User>('/auth/me/'),
  signup: (body: Record<string, string>) => request<SignupResponse>('/auth/signup/', { method: 'POST', body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) => request<AuthPayload>('/auth/login/', { method: 'POST', body: JSON.stringify(body) }),
  verifyEmail: (token: string) => request<AuthPayload>('/auth/verify-email/', { method: 'POST', body: JSON.stringify({ token }) }),
  resendVerification: (email: string) => request<{ detail: string }>('/auth/resend-verification/', { method: 'POST', body: JSON.stringify({ email }) }),
  requestPasswordReset: (email: string) => request<{ detail: string }>('/auth/password-reset/request/', { method: 'POST', body: JSON.stringify({ email }) }),
  confirmPasswordReset: (token: string, password: string) => request<{ detail: string }>('/auth/password-reset/confirm/', { method: 'POST', body: JSON.stringify({ token, password }) }),
  logout: () => request<void>('/auth/logout/', { method: 'POST' }),
  deleteCandidateAccount: (password: string, confirmation: string) => request<void>('/candidate/account/', { method: 'DELETE', body: JSON.stringify({ password, confirmation }) }),
  candidateProfile: () => request<Candidate>('/candidate/profile/'),
  updateCandidate: (body: Partial<Candidate>) => request<Candidate>('/candidate/profile/', { method: 'PATCH', body: JSON.stringify(body) }),
  submitCandidate: (consent: boolean) => request<Candidate>('/candidate/profile/submit/', { method: 'POST', body: JSON.stringify({ consent }) }),
  uploadResume: (file: File) => { const body = new FormData(); body.append('file', file); return request<Candidate>('/candidate/resumes/', { method: 'POST', body }) },
  retryResume: (id: number) => request<Candidate>(`/candidate/resumes/${id}/retry/`, { method: 'POST' }),
  searches: () => request<Search[]>('/searches/'),
  createSearch: (query: string, project?: number) => request<Search>('/searches/', { method: 'POST', body: JSON.stringify({ query, project }) }),
  answerSearch: (id: number, answer: string) => request<Search>(`/searches/${id}/answer/`, { method: 'POST', body: JSON.stringify({ answer }) }),
  results: (id: number, filters = '') => request<{ count: number; results: SearchResult[]; search: Search }>(`/searches/${id}/results/${filters}`),
  candidate: (id: number) => request<Candidate>(`/candidates/${id}/`),
  setStatus: (id: number, status: string, reason = '', note = '') => request(`/candidates/${id}/status/`, { method: 'PUT', body: JSON.stringify({ status, reason, note }) }),
  clearStatus: (id: number) => request<void>(`/candidates/${id}/status/`, { method: 'DELETE' }),
  compare: (candidate_ids: number[]) => request<Candidate[]>('/candidates/compare/', { method: 'POST', body: JSON.stringify({ candidate_ids }) }),
  notifications: () => request<Notification[]>('/notifications/'),
  markNotificationRead: (id: number) => request<void>(`/notifications/${id}/read/`, { method: 'POST' }),
  projects: () => request<Project[]>('/projects/'),
  createProject: (name: string, description = '') => request<Project>('/projects/', { method: 'POST', body: JSON.stringify({ name, description }) }),
  project: (id: number) => request<ProjectDetail>(`/projects/${id}/`),
  addCandidateToProject: (projectId: number, candidateId: number) => request(`/projects/${projectId}/candidates/`, { method: 'POST', body: JSON.stringify({ candidate_id: candidateId }) }),
  removeCandidateFromProject: (projectId: number, candidateId: number) => request<void>(`/projects/${projectId}/candidates/${candidateId}/`, { method: 'DELETE' }),
}
