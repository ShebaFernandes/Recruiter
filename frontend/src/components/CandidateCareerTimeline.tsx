import type { WorkExperience } from '../types'
import CareerJourney from './CareerJourney'

export default function CandidateCareerTimeline({ items }: { items: WorkExperience[] }) {
  return <CareerJourney items={items} detailed />
}
