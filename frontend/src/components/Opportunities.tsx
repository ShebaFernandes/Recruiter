import '../platform-styles.css'
import { api } from '../api'
import { applicationCvReady } from '../opportunityApplication'
import OpportunityApplication from './OpportunityApplication'
import { navigateSmoothly } from './smoothPageNavigation'
import SiteFooter from './SiteFooter'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { ArrowUp, LogOut, X } from 'lucide-react'
import EnterLogo from './EnterLogo'
import './opportunities.css'

import { roles } from './opportunityRoles'
const experienceBands = ['upto 3', '3-6', '6-10', '10-15', '15-20', '20+']
function experienceBand(value: string) {
 const years = parseFloat(value)
 if (!Number.isFinite(years)) return ''
 if (years <= 3) return 'upto 3'
 if (years < 6) return '3-6'
 if (years < 10) return '6-10'
 if (years < 15) return '10-15'
 if (years < 20) return '15-20'
 return '20+'
}
const categories = [ 'Engineering', 'AI & ML', 'Founding', 'Product', 'Leadership', 'Business & GTM']
const trackLabels: Record<string,string> = { 'AI & ML': 'AI / ML', Product: 'Product & Design', Founding: 'Founding & 0→1' }
const additionalTracks: Record<string,string[]> = {
 'founding-backend-engineer': ['Engineering'],
 'founding-full-stack-engineer': ['Engineering'],
 'founding-ai-evals-engineer': ['Founding'],
 'lead-product-manager-consumer': ['Leadership'],
 'lead-product-manager-consumer-healthtech': ['Leadership'],
 'lead-product-manager-b2b-growth': ['Leadership'],
}
const engineeringSections = ['Backend Engineer', 'Frontend Engineer', 'Full Stack Engineer', 'Mobile Engineer', 'DevOps/SRE', 'QA/SDET', 'Deployment/Solution Engineer', 'Security Engineer', 'Data']
const engineeringRoleSections: Record<string, string> = {
 'founding-backend-engineer': 'Backend Engineer',
 'founding-full-stack-engineer': 'Full Stack Engineer',
 'backend-engineer': 'Backend Engineer',
 'senior-backend-engineer': 'Backend Engineer',
 'frontend-engineer-sde-iii': 'Frontend Engineer',
 'mobile-engineer-flutter': 'Mobile Engineer',
 'senior-sre-devops-engineer': 'DevOps/SRE',
}
type Opportunity = (typeof roles)[number]
function OpportunityFacts({ role, listing = false }: { role: Opportunity; listing?: boolean }) {
 const facts = [
  ['Salary', role.salary || 'Not specified'],
  ['Location', role.location || 'Not specified'],
  ['Experience', /years/.test(role.experience) ? role.experience : 'Not specified'],
  ['Openings', role.openings ? String(role.openings) : 'Not specified'],
  ['Work mode', role.mode || 'Not specified'],
 ]
 return <dl className="opp-facts">{facts.filter(([label]) => !listing || label !== 'Work mode').map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
}
export default function Opportunities({loggedIn, onLogin, embedded = false, onDetailClose, applicationDetails = false}: {loggedIn:boolean;onLogin:()=>void;embedded?:boolean;onDetailClose?:()=>void;applicationDetails?:boolean}) {
 const [applying,setApplying]=useState(false)
 const [submitting, setSubmitting] = useState(false)
 const submitLock = useRef(false)
 const [applicationResults, setApplicationResults] = useState<Record<string, {message:string;success:boolean}>>({})
 useEffect(() => {
   if (!loggedIn) return
   let active = true
   api.opportunityApplications().then(items => {
     if (!active) return
     setApplicationResults(current => {
       const saved = { ...current }
       for (const item of items) saved[item.opportunity_id] = { message: 'Already applied', success: true }
       return saved
     })
   }).catch(() => { /* Submission still checks duplicates on the server. */ })
   return () => { active = false }
 }, [loggedIn])
 const [category,setCategory]=useState('All opportunities')
 const [engineeringSection,setEngineeringSection]=useState('All engineering')
 const [search,setSearch]=useState('')
 const [location,setLocation]=useState('')
 const [experience,setExperience]=useState('')
 const [mode,setMode]=useState('')
 const [selected,setSelected]=useState<string|null>(sessionStorage.getItem('enter-opportunity-intent') || new URLSearchParams(window.location.search).get('role'))
 const panelRef = useRef<HTMLElement>(null)
 const role=roles.find(item=>item.id===selected)
 const detailClosed = useEffectEvent(() => onDetailClose?.())
 useEffect(() => {
   if (!role || applying) return
   const previousOverflow = document.body.style.overflow
   const opener = document.activeElement as HTMLElement | null
   document.body.style.overflow = 'hidden'
   panelRef.current?.focus({ preventScroll: true })
   const keyboard = (event: KeyboardEvent) => {
     if (event.key === 'Escape') {
       event.preventDefault()
       setSelected(null); setApplying(false)
       sessionStorage.removeItem('enter-opportunity-intent')
       detailClosed()
       return
     }
     if (event.key !== 'Tab') return
     const controls = Array.from(panelRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]):not([hidden]), a[href], textarea, input, select') || []).filter(element => element.getClientRects().length > 0)
     const first = controls[0], last = controls[controls.length - 1]
     if (!first) { event.preventDefault(); return }
     if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) { event.preventDefault(); last.focus() }
     else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
   }
   document.addEventListener('keydown', keyboard)
   return () => {
     document.removeEventListener('keydown', keyboard)
     document.body.style.overflow = previousOverflow
     if (opener?.isConnected) opener.focus({ preventScroll: true })
   }
 }, [role, applying])
 const visible=roles.filter(item=>(category !== 'Engineering' || engineeringSection === 'All engineering' || engineeringRoleSections[item.id] === engineeringSection) && (category==='All opportunities' || (item.category===category || additionalTracks[item.id]?.includes(category))) && `${item.title} ${item.domain} ${item.skills.join(' ')}`.toLowerCase().includes(search.toLowerCase()) && (!location || item.location===location) && (!experience || experienceBand(item.experience)===experience) && (!mode || item.mode===mode))
 async function apply(){
   if (!role || submitLock.current || applicationDetails) return
   const id = role.id
   if (!loggedIn) { sessionStorage.setItem('enter-opportunity-intent', id); onLogin(); return }
   submitLock.current = true; setSubmitting(true)
   try {
     const profile = await api.candidateProfile()
     if (!applicationCvReady(profile)) { setApplying(true); return }
     const result = await api.applyOpportunity(id, '')
     setApplicationResults(current => ({...current, [id]:{message:result.detail,success:true}}))
     sessionStorage.removeItem('enter-opportunity-intent')
   } catch (cause) {
     setApplicationResults(current => ({...current, [id]:{message:cause instanceof Error ? cause.message : 'Could not apply. Please try again.',success:false}}))
   } finally { submitLock.current = false; setSubmitting(false) }
 }


 if (role && applying && loggedIn) return <OpportunityApplication embedded={embedded} key={role.id} role={role} onBack={() => { setApplying(false); setSelected(null); sessionStorage.removeItem('enter-opportunity-intent'); const url = new URL(window.location.href); url.searchParams.delete('role'); window.history.replaceState({}, '', url.pathname + url.search); window.scrollTo(0, 0) }} />
 return <main className={`opportunities-page${role ? ' has-opportunity-panel' : ''}`}><header className="opp-header"><a href="/" aria-label="Enter home"><EnterLogo /></a><nav><a className="opp-back-home" href="/" onClick={navigateSmoothly}>Back to enter <LogOut size={16}/></a></nav></header>
 <div className="opp-browse"><section className="opp-hero"><p className="opp-eyebrow">OPPORTUNITIES</p><h1>Find something worth<br/>building next.</h1><p>Explore opportunities across Engineering, AI &amp; ML, Founding, Product,<br className="opp-desktop-break"/> Design, Leadership and Business.</p></section>
 <section id="opportunity-list" className="opp-directory"><div className="opp-tabs" role="tablist" aria-label="Opportunity categories">{categories.map(item=><button key={item} role="tab" aria-selected={category===item} onClick={()=>{setCategory(item);setEngineeringSection('All engineering');setSelected(null);setApplying(false)}}>{trackLabels[item] || item}</button>)}</div>{category === 'Engineering' && <div className="opp-subsections" role="group" aria-label={`${category} specialisms`}>{engineeringSections.map(section => <button type="button" key={section} aria-pressed={engineeringSection === section} onClick={() => { setEngineeringSection(section); setSelected(null); setApplying(false) }}>{section}</button>)}</div>}<div className="opp-tools"><input type="search" aria-label="Search opportunities" placeholder="Search role, skill or domain..." value={search} onChange={event=>setSearch(event.target.value)}/><select aria-label="Location" value={location} onChange={event=>setLocation(event.target.value)}><option value="" hidden>Location</option>{[...new Set(roles.map(role => role.location).filter(Boolean))].map(value => <option key={value}>{value}</option>)}</select><select aria-label="Experience" value={experience} onChange={event=>setExperience(event.target.value)}><option value="" hidden>Experience</option>{experienceBands.map(item=><option key={item}>{item}</option>)}</select><select aria-label="Work mode" value={mode} onChange={event=>setMode(event.target.value)}><option value="" hidden>Work Mode</option>{[...new Set(roles.map(role => role.mode).filter(Boolean))].map(value => <option key={value}>{value}</option>)}</select></div><div className="opp-result-summary"><p className="opp-count" aria-live="polite">{visible.length} {visible.length===1?'opportunity':'opportunities'}</p>{(search || location || experience || mode) && <button className="opp-clear" onClick={()=>{setSearch('');setLocation('');setExperience('');setMode('');setSelected(null)}}>Clear filters</button>}</div><div className="opp-results">{role && <div className="opp-detail-layout" role="dialog" aria-modal="true" aria-label="Job description"><aside className="opp-summary" aria-label="Opportunity summary"><p className="opp-summary-title">{role.title}</p><p className="opp-summary-category">{role.category}</p><OpportunityFacts role={role} listing /><div className="opp-tags">{role.skills.map(skill => <span key={skill}>{skill}</span>)}</div></aside><section ref={panelRef} tabIndex={-1} className={`opp-detail${applicationDetails ? ' is-application-details' : ''}`} aria-label="Full job description"><button type="button" className="opp-panel-close" aria-label="Close job description" onClick={()=>{setSelected(null);setApplying(false);sessionStorage.removeItem('enter-opportunity-intent');onDetailClose?.()}}><X size={20}/></button><p className="opp-eyebrow">{role.category}</p><h2 className="opp-detail-title">{role.title}</h2>{'description' in role ? <p>{role.description}</p> : <p className="opp-detail-note">The available role details are listed below. Join the Talent Network to discuss the opportunity with our team.</p>}<h2>Non-negotiables</h2><div className="opp-tags">{role.skills.map(skill=><span key={skill}>{skill}</span>)}</div>{'standout' in role && <><h2>What will make you stand out</h2><p>{role.standout}</p><h2>What’s not working in this search</h2><p>{role.mismatch}</p><h2>Interviews are likely to go deep on</h2><div className="opp-tags">{role.interviews?.map(skill=><span key={skill}>{skill}</span>)}</div></>}{'expect' in role && Boolean(role.expect?.length) && <><h2>Expect to discuss</h2><ul className="opp-discussion">{role.expect?.map(topic => <li key={topic}>{topic}</li>)}</ul></>}{'techEnvironment' in role && Boolean(role.techEnvironment?.length) && <><h2>Tech environment</h2><div className="opp-tags">{role.techEnvironment?.map(item => <span key={item}>{item}</span>)}</div></>}{applicationDetails && <p className="opp-application-result" role="status">Application submitted</p>}{applicationResults[role.id] && <p className="opp-application-result" role={applicationResults[role.id].success ? 'status' : 'alert'}>{applicationResults[role.id].message}</p>}<button className="opp-apply" hidden={applying || applicationDetails} disabled={submitting || applicationResults[role.id]?.success} onClick={() => void apply()}>{submitting ? 'Applying…' : applicationResults[role.id]?.success ? 'Already applied' : 'Apply now'}</button></section></div>}<div className="opp-role-list">{visible.map(item=><article className={`opp-row${item.id === selected ? ' is-selected' : ''}`} key={item.id}><div><h2><button onClick={()=>{setSelected(item.id);setApplying(false);requestAnimationFrame(()=>{panelRef.current?.scrollTo(0,0);panelRef.current?.focus({preventScroll:true})})}}>{item.title}</button></h2><p className="opp-role-context">{[item.category,item.mode].filter(Boolean).join(' · ')}</p>{applicationResults[item.id]?.success && <span className="opp-applied-badge">Already applied</span>}</div><div className="opp-row-body"><OpportunityFacts role={item} listing /><div className="opp-list-skills">{item.skills.map(skill => <span key={skill}>{skill}</span>)}</div></div><div className="opp-actions"><button className="opp-link" onClick={()=>{setSelected(item.id);setApplying(false);requestAnimationFrame(()=>{panelRef.current?.scrollTo(0,0);panelRef.current?.focus({preventScroll:true})})}}>View Opportunity</button></div></article>)}{visible.length===0 && <p className="opp-empty">No matching opportunities. Try another search or filter.</p>}</div></div></section></div>
 <section className="opp-discover" aria-labelledby="opp-discover-title"><div><p className="opp-eyebrow">STAY DISCOVERABLE</p><h2 id="opp-discover-title">Nothing here feels quite right?</h2></div><div className="opp-discover-copy"><p>Some searches never make it to the public page, and new opportunities open all the time.</p><p>Tell us what you’ve done and what you’d like to do next. When something relevant comes up, we’ll know where to find you.</p><button className="opp-network-button" onClick={() => { sessionStorage.removeItem('enter-opportunity-intent'); setSelected(null); setApplying(false); onLogin() }}>Join ENTER’s Talent Network</button></div></section>
 <section className="opp-next" aria-labelledby="opp-next-title"><p className="opp-eyebrow">WHAT HAPPENS NEXT</p><h2 id="opp-next-title">One conversation, started well.</h2><ol className="opp-steps">{[
 ['Join the Talent Network','Start with your CV and profile.'],
 ['We understand your work','Beyond skills and titles.'],
 ['We find the intersection','Your experience × the right opportunity.'],
 ['We reach out','When there’s something worth talking about.'],
 ].map(([title,description],index)=><li key={title}><span className="opp-step-number">0{index+1}</span><h3>{title}</h3><p>{description}</p></li>)}</ol></section>
 <section className="opp-bottom-actions" aria-label="Explore or join"><a className="opp-link" href="#opportunity-list">Explore Opportunities <ArrowUp size={18}/></a><button className="opp-network-button" onClick={() => { sessionStorage.removeItem('enter-opportunity-intent'); setSelected(null); setApplying(false); onLogin() }}>Join ENTER’s Talent Network</button></section>
 <SiteFooter compact /></main>
}
