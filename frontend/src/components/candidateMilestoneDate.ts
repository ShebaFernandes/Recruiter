import type { WorkExperience } from '../types'
import { careerStartYear } from '../careerHistory'

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Compact visible milestones; use month precision only to disambiguate a shared year. */
export function candidateMilestoneDate(item: WorkExperience, includeMonth = false) {
  const year = careerStartYear(item)
  if (!year) return 'Date unknown'
  const stored = item.start_date?.match(/^(?:19|20)\d{2}-(0[1-9]|1[0-2])(?:-|$)/)
  if (includeMonth && stored) return `${months[Number(stored[1]) - 1]} ${year}`
  return year
}
