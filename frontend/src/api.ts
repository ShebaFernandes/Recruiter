import type { Candidate, Notification, Project, ProjectDetail, Search, SearchResult, User } from './types'

export type AuthPayload = { token: string; user: User }
export type SignupResponse = AuthPayload | { detail: string; requires_email_verification: true }

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'

export const auth = {
  token: () => localStorage.getItem('enter_token'),
  user: (): User | null => {
    try { return JSON.parse(localStorage.getItem('enter_user') || 'null') as User | null } catch { return null }
  },
  save: (payload: AuthPayload) => {
    localStorage.setItem('enter_token', payload.token)
    localStorage.setItem('enter_user', JSON.stringify(payload.user))
  },
  clear: () => {
    localStorage.removeItem('enter_token')
    localStorage.removeItem('enter_user')
  },
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = auth.token()
  if (token) headers.set('Authorization', `Token ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (response.status === 401) auth.clear()
  if (!response.ok) {
    let message = 'The request could not be completed.'
    try {
      const body = await response.json()
      message = body.detail || Object.values(body).flat().join(' ') || message
    } catch { /* preserve fallback */ }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
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
  searches: () => request<Search[]>('/searches/'),
  createSearch: (query: string, project?: number) => request<Search>('/searches/', { method: 'POST', body: JSON.stringify({ query, project }) }),
  answerSearch: (id: number, answer: string) => request<Search>(`/searches/${id}/answer/`, { method: 'POST', body: JSON.stringify({ answer }) }),
  results: (id: number, filters = '') => request<{ count: number; results: SearchResult[]; search: Search }>(`/searches/${id}/results/${filters}`),
  candidate: (id: number) => request<Candidate>(`/candidates/${id}/`),
  setStatus: (id: number, status: string) => request(`/candidates/${id}/status/`, { method: 'PUT', body: JSON.stringify({ status }) }),
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
