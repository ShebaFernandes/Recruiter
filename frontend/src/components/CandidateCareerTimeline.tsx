import type { EmploymentExtraction, WorkExperience } from '../types'
import CareerJourney from './CareerJourney'

export default function CandidateCareerTimeline({ items, edit, reviewLatestResume, extraction }: { items: WorkExperience[]; edit?: () => void; reviewLatestResume?: () => void; extraction?: EmploymentExtraction | null }) {
  const stale = extraction?.stale_profile_preserved
  const hasTimeline = items.length > 0
  return <section className="cp-career" aria-labelledby="candidate-career-heading">
    <div className="cp-career-heading"><div><h3 id="candidate-career-heading">Your career journey</h3><p>{hasTimeline ? 'Employment dates to scale. Scroll to explore; hover or tap a role for details.' : 'Latest resume verification and safely retained records.'}</p></div></div>
    <div className={stale ? 'cp-career-previous' : ''}><CareerJourney items={items} extraction={extraction} profilePresentation presentAtEnd candidateMilestones /></div>
    {extraction?.profile_state === 'pending_candidate_review' && reviewLatestResume
      ? <button type="button" onClick={reviewLatestResume}>Review roles from latest resume</button>
      : (!items.length || extraction?.stale_profile_preserved || extraction?.status === 'review_required') && edit && <button type="button" onClick={edit}>Review saved profile</button>}
  </section>
}
