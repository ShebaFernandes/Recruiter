import type { WorkExperience } from '../types'
import { careerStartYear } from '../careerHistory'

/** Compact visible milestones; full saved dates remain in the detail popover. */
export function candidateMilestoneDate(item: WorkExperience) {
  return careerStartYear(item) || 'Date unknown'
}
