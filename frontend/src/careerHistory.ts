import type { WorkExperience } from './types'

/** Both audiences use the same chronology; unknown starts sort last, never to 1970. */
export function sortCareerHistory(items: WorkExperience[]) {
  return [...items].sort((a, b) => (a.start_date || '9999').localeCompare(b.start_date || '9999'))
}
