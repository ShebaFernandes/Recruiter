import SiteFooter from './SiteFooter'
import { type FormEvent, useRef, useState } from 'react'
import { ChevronDown, Check, LogOut, ArrowUpRight, ArrowLeft } from 'lucide-react'
import { api } from '../api'
import EnterLogo from './EnterLogo'
import './careers.css'
import { careerPositions, careerDepartments, careerLocations } from './careerPositions'

export default function Careers() {
  const [department, setDepartment] = useState('All departments')
  const [location, setLocation] = useState('All locations')
  const [position, setPosition] = useState('')
  const [activeJob, setActiveJob] = useState<(typeof careerPositions)[number] | null>(null)
  const [search, setSearch] = useState('')
  const [applicationOpen, setApplicationOpen] = useState(false)
  const visiblePositions = careerPositions.filter(job => (department === 'All departments' || job.department === department) && (location === 'All locations' || job.location === location) && `${job.title} ${job.summary}`.toLowerCase().includes(search.toLowerCase()))
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const submitting = useRef(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current || submitted) return
    const form = event.currentTarget
    const body = new FormData(form)
    if (position) body.set('motivation', `Position: ${position}\n\n${body.get('motivation') ?? ''}`)
    const resume = body.get('resume')
    if (resume instanceof File && (resume.size > 10 * 1024 * 1024 || !/\.(pdf|docx)$/i.test(resume.name))) {
      setMessage('Choose a PDF or DOCX resume smaller than 10 MB.')
      return
    }
    submitting.current = true
    setSending(true)
    setMessage('')
    try {
      const result = await api.submitCareerApplication(body)
      setMessage(result.detail)
      setSubmitted(true)
      form.reset()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Please try again.')
    } finally {
      submitting.current = false
      setSending(false)
    }
  }
  return <main className="enter-careers">
    <a className="careers-skip" href="#positions">Skip to open positions</a>
    <div className="careers-hero-surface"><MountainScene /><header><a href="/" aria-label="Enter home"><EnterLogo /><span className="careers-tagline">Humanity. Integrity and Possibility.</span></a><nav aria-label="Careers navigation"><a href="/careers" aria-current="page">Careers</a><a href="/">Back to enter <LogOut size={16} strokeWidth={1.5} aria-hidden="true" /></a></nav></header>
    <section className="careers-hero"><p className="careers-eyebrow">CAREERS</p><h1 tabIndex={-1}>Hiring as We Know It Is Broken.<br /><span>Be a Part of the Team Fixing It.</span></h1><p>Be a part of enter.</p></section></div>
    <div className="careers-workspace"><section id="positions" className="careers-positions"><div><p className="careers-eyebrow">BUILD WHAT COMES NEXT</p><h2>Open Positions</h2></div><div className="careers-filters"><CareerFilter label="Department" value="All departments" options={careerDepartments} onChange={setDepartment} /><CareerFilter label="Location" value="All locations" options={careerLocations} onChange={setLocation} /></div><label className="careers-role-search">Search roles<input type="search" placeholder="Find your next role" value={search} onChange={event => setSearch(event.target.value)} /></label><div className="careers-job-list" aria-live="polite"><p className="careers-role-count">{visiblePositions.length} open roles</p>{careerDepartments.map(dept => { const jobs = visiblePositions.filter(job => job.department === dept); return jobs.length > 0 && <section className="careers-department" key={dept}><h3>{dept}<span>{jobs.length} {jobs.length === 1 ? 'role' : 'roles'}</span></h3><div>{jobs.map(job => <button type="button" className="careers-role-row" key={job.id} onClick={() => { setActiveJob(job); setApplicationOpen(false); setPosition(`${job.title} · ${job.department} · ${job.location}`) }}><span className="careers-role-title">{job.title}</span><span className="careers-role-location">{job.location}</span><ArrowUpRight size={19} aria-hidden="true" /></button>)}</div></section> })}{visiblePositions.length === 0 && <div className="careers-empty"><h3>No matching positions</h3><p>Try another search, department, or location.</p></div>}</div></section>

    {(activeJob || applicationOpen) && <section className="careers-job-page" aria-label="Job details"><div className="careers-job-page-inner"><div className="careers-job-page-header"><button type="button" aria-label="Back to open positions" onClick={() => { setActiveJob(null); setApplicationOpen(false) }}><ArrowLeft size={22} /></button><a href="/" aria-label="Enter home"><EnterLogo /></a></div><h1>{activeJob?.title || 'Apply to enter'}</h1><div className="careers-job-page-layout"><aside className="careers-job-facts"><dl><div><dt>Location</dt><dd>{activeJob?.location || 'Not specified'}</dd></div><div><dt>Department</dt><dd>{activeJob?.department || 'Future opportunities'}</dd></div></dl></aside><div className="careers-job-page-content"><div className="careers-job-tabs" role="tablist" aria-label="Job information"><button type="button" role="tab" id="career-overview-tab" aria-controls="career-overview" aria-selected={!applicationOpen} disabled={!activeJob} onClick={() => setApplicationOpen(false)}>Overview</button><button type="button" role="tab" id="career-application-tab" aria-controls="career-application-panel" aria-selected={applicationOpen} onClick={() => setApplicationOpen(true)}>Application</button></div><div id="career-overview" role="tabpanel" aria-labelledby="career-overview-tab" hidden={applicationOpen}><div className="careers-job-description">{activeJob?.sections.map(section => <section key={section.title}><h4>{section.title}</h4>{'text' in section && <p>{section.text}</p>}{'items' in section && <ul>{section.items?.map(item => <li key={item}>{item}</li>)}</ul>}</section>)}<button type="button" className="careers-action" onClick={() => setApplicationOpen(true)}>Apply for this role <ArrowUpRight size={16} /></button></div></div><div id="career-application-panel" role="tabpanel" aria-labelledby="career-application-tab" hidden={!applicationOpen}><form id="career-application" onSubmit={submit} aria-busy={sending}><p className="careers-eyebrow">APPLY</p><h2>Apply to enter</h2><p className="careers-note">Send us your details and resume to be considered for future opportunities at enter.</p><div className="careers-fields"><label className="careers-wide">Position<select aria-label="Position" value={position} onChange={event => setPosition(event.target.value)}><option value="">Future opportunities</option>{careerPositions.map(job => { const value = `${job.title} · ${job.department} · ${job.location}`; return <option key={job.id} value={value}>{value}</option> })}</select></label><label>Name<input placeholder="Your full name" name="name" autoComplete="name" required /></label><label>Email<input placeholder="you@example.com" name="email" type="email" autoComplete="email" required /></label><label>Phone<input placeholder="Your phone number" name="phone" type="tel" autoComplete="tel" required /></label><label>LinkedIn Profile<input name="linkedin" type="url" placeholder="https://www.linkedin.com/in/your-profile" required /></label><label className="careers-wide">Resume Upload<input name="resume" type="file" accept=".pdf,.docx" required /><small>PDF or DOCX · Maximum 10 MB</small></label><label className="careers-wide">Why ENTER?<textarea name="motivation" rows={4} required placeholder="Tell us what you would love to build with us." /></label></div><button className="careers-action" type="submit" disabled={sending || submitted}>{sending ? 'Submitting…' : submitted ? 'Application received ✓' : 'Apply Now'}</button><p role="status">{message}</p></form></div></div></div></div></section>}
    <section className="careers-application careers-apply-invite"><p className="careers-eyebrow">YOUR NEXT CHAPTER</p><h2>Great people create a brighter tomorrow.</h2><p>Don’t see the right role? We’d still love to hear from you.</p><button type="button" className="careers-action" onClick={() => { setPosition(''); setActiveJob(null); setApplicationOpen(true) }}>Apply to enter <ArrowUpRight size={16} /></button></section>
</div><SiteFooter />
  </main>
}


function MountainScene() {
  return <div className="careers-scene" aria-hidden="true"><img src="/media/section10-closing-mountain-lush.png" alt="" width={2048} height={819} /></div>
}


function CareerFilter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  const [selected, setSelected] = useState(value)
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const option = useRef<HTMLButtonElement>(null)
  return <div className="careers-filter" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }} onKeyDown={event => {
    if (event.key === 'Escape') { setOpen(false); trigger.current?.focus() }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('.careers-filter-panel button'))
      const current = buttons.indexOf(document.activeElement as HTMLButtonElement)
      const next = event.key === 'ArrowDown' ? (current + 1) % buttons.length : (current <= 0 ? buttons.length - 1 : current - 1)
      requestAnimationFrame(() => buttons[next]?.focus())
    }
  }}>
    <span id={`careers-filter-${label}`}>{label}</span>
    <button ref={trigger} type="button" className="careers-filter-trigger"
      aria-labelledby={`careers-filter-${label} careers-filter-value-${label}`}
      aria-expanded={open} aria-controls={`careers-filter-panel-${label}`}
      onClick={() => setOpen(current => !current)}>
      <span id={`careers-filter-value-${label}`}>{selected}</span><ChevronDown size={16} aria-hidden="true" />
    </button>
    <div id={`careers-filter-panel-${label}`} className={`careers-filter-panel${open ? ' is-open' : ''}`} inert={!open}>
      {[value, ...options].map((item, index) => <button key={item} ref={index === 0 ? option : undefined} type="button" aria-pressed={selected === item} onClick={() => { setSelected(item); onChange(item); setOpen(false); trigger.current?.focus() }}>
        {item}{selected === item && <Check size={15} aria-hidden="true" />}
      </button>)}
    </div>
  </div>
}
