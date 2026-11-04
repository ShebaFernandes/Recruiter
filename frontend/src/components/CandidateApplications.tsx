import { ArrowRight, CalendarDays, Check, FileText, MapPin } from 'lucide-react'
import { roles } from './Opportunities'
import './candidate-applications.css'

type Application = { id: number; opportunity_id: string; created_at: string }
export default function CandidateApplications({ applications, loading, error, browse, view }: {
  applications: Application[]; loading: boolean; error: string; browse: () => void; view: (id: string) => void
}) {
  return <main className="candidate-applications">
    <h1>My Applications</h1><p className="applications-intro">Follow every opportunity, from application to outcome.</p>
    {!loading && !error && <div className="applications-summary">
      <div><FileText aria-hidden="true" /><strong>{applications.length}</strong><span>Total applications</span></div>
      <div><Check aria-hidden="true" /><strong>{applications.length}</strong><span>Submitted</span></div>
    </div>}
    {loading ? <p role="status">Loading applications…</p> : error ? <p role="alert">{error}</p> : applications.length ? <ul className="application-list">{applications.map(item => {
      const role = roles.find(role => role.id === item.opportunity_id)
      return <li key={item.id} className="application-card">
        <div className="application-card-heading"><div><h2>{role?.title || item.opportunity_id}</h2><p className="application-meta">{role?.location && <span><MapPin aria-hidden="true" />{role.location}</span>}<span><CalendarDays aria-hidden="true" />Applied on {new Date(item.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}</span></p></div>
          <span className="application-status"><Check aria-hidden="true" />Submitted</span>
          <button onClick={() => view(item.opportunity_id)}>View details <ArrowRight aria-hidden="true" /></button>
        </div>
        <ol className="application-progress" aria-label="Application progress"><li aria-current="step"><span><Check aria-hidden="true" /></span>Applied</li><li><span />In review</li><li><span />Interview</li><li><span />Decision</li></ol>
      </li>
    })}</ul> : <section className="application-empty"><h2>Your next opportunity starts here.</h2><p>You haven’t applied to any opportunities yet.</p><button onClick={browse}>Browse opportunities <ArrowRight aria-hidden="true" /></button></section>}
  </main>
}
