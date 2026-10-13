import type { Candidate } from './types'
import { sortCareerHistory } from './careerHistory'

// Old extracted profiles can contain prose in role fields. Keep saved data intact,
// but never present an achievement paragraph as an identity or prediction.
export function isConciseIdentity(value: string) {
  return value.length > 0 && value.length <= 125 && value.split(/\s+/).length <= 18 && !/^(built|led|shipped|architected|delivered|developed|created|improved|responsible|owned|drove)\b/i.test(value) && !/[.!?]\s/.test(value)
}

export function professionalTitle(profile: Pick<Candidate, 'headline' | 'work_experiences'>) {
  if (isConciseIdentity(profile.headline)) return profile.headline
  return sortCareerHistory(profile.work_experiences).filter(row => row.start_date).reverse().find(row => isConciseIdentity(row.role))?.role || ''
}

export function likelyDirections(profile: Pick<Candidate, 'headline' | 'work_experiences' | 'career_preferences'>) {
  // An explicitly saved empty list is an intentional candidate correction.
  if (profile.career_preferences?.likely_directions !== undefined) return profile.career_preferences.likely_directions.filter(isConciseIdentity)
  const title = professionalTitle(profile)
  const leadership = /\b(manager|director|head|lead|leader|president|AVP|CTO)\b/i.test(title)
  if (leadership && /\b(engineering|engineer|technical)\b/i.test(title)) {
    return [/\b(AI|machine learning|data science)\b/i.test(title) ? 'AI Engineering Leadership' : /\bplatform\b/i.test(title) ? 'Platform Leadership' : 'Engineering Leadership']
  }
  if (/\b(senior|staff|principal)\b/i.test(title) && /\bengineer\b/i.test(title)) return ['Staff Engineering']
  return []
}
