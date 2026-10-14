import type { WorkExperience } from '../types'
import CareerJourney from './CareerJourney'

export default function CandidateCareerTimeline({ items, edit }: { items: WorkExperience[]; edit?: () => void }) {
  return <section className="cp-career" aria-labelledby="candidate-career-heading">
    <div className="cp-career-heading"><div><h3 id="candidate-career-heading">Your career journey</h3><p>A visual timeline from your resume. Hover or tap a role for details.</p></div></div>
    {items.length > 0 ? <CareerJourney items={items} compactMarkers showCompanyLabels={false} minimal presentAtEnd /> : <div className="cp-career-empty">
      <p>We couldn't confidently identify employment history from this resume.</p>
      {edit && <button type="button" onClick={edit}>Add career history</button>}
    </div>}
  </section>
}
