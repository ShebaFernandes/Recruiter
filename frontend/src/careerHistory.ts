import type { WorkExperience } from './types'

export function careerStartYear(item: WorkExperience) {
  const stored = item.start_date?.match(/^(?:19|20)\d{2}/)?.[0]
  if (stored) return stored
  return item.date_label?.match(/^\s*((?:19|20)\d{2})(?!\d)/)?.[1] || null
}

function careerStartKey(item: WorkExperience) {
  if (item.start_date) return item.start_date
  const year = careerStartYear(item)
  // Sorting by a coarse year is presentation-only. The database date remains null,
  // so the UI never turns a year-only resume claim into a fictitious January date.
  return year ? `${year}-00-00` : '9999'
}

/** Both audiences use the same chronology; genuinely unknown starts sort last. */
export function sortCareerHistory(items: WorkExperience[]) {
  return [...items].sort((a, b) => careerStartKey(a).localeCompare(careerStartKey(b)))
}
