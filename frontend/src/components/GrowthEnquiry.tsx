import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, ChevronDown, X } from 'lucide-react'
import { api } from '../api'

type GrowthKind = 'founding' | 'leadership'

const foundingOptions = ['Founding Engineer', 'Founding AI / ML', 'Early Technical Leader (CTO / Head of Eng)', 'Founding Designer', 'Other +']
const leadershipOptions = ['Engineering Leader', 'Product Leader', 'Business Leader', 'Other +']

function GrowthDropdown({ label, name, options, optional }: { label: string; name: string; options: string[]; optional: boolean }) {
  const [value, setValue] = useState('')
  const dropdownRef = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    const close = (event: MouseEvent) => {
      const dropdown = dropdownRef.current
      if (dropdown && !dropdown.contains(event.target as Node)) dropdown.open = false
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return <label className="growth-enquiry__field"><span>{label}</span><div className="growth-dropdown"><input className="growth-dropdown__value" aria-label={label} name={name} value={value} required={!optional} onChange={() => {}} tabIndex={-1} /><details ref={dropdownRef} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() } }} name="founding-dropdown" onToggle={event => { if (event.currentTarget.open) { const current = event.currentTarget; current.closest('form')?.querySelectorAll('details[open]').forEach(item => { if (item !== current) item.removeAttribute('open') }); requestAnimationFrame(() => current.querySelector('.growth-dropdown__menu')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })) } }}><summary><span className="growth-dropdown__text">{value || (name === 'people_count' ? 'Select team size' : name === 'equity_range' ? 'Select equity' : name === 'cash_range' ? 'Select cash range' : `Choose ${label.toLowerCase()}`)}</span><ChevronDown size={14} strokeWidth={1.8} aria-hidden="true" /></summary><div className="growth-dropdown__menu">{options.map(option => <button type="button" key={option} aria-pressed={value === option} onClick={() => { setValue(option); const dropdown = dropdownRef.current; if (dropdown) { dropdown.open = false; dropdown.querySelector('summary')?.focus() } }}>{option}</button>)}</div></details></div></label>
}

export default function GrowthEnquiry({ kind, onClose }: { kind: GrowthKind; onClose: () => void }) {
  const founding = kind === 'founding'
  const [selected, setSelected] = useState<string[]>([])
  const [otherRole, setOtherRole] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [attachment, setAttachment] = useState<File | null>(null)
  const [submitState, setSubmitState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const options = founding ? foundingOptions : leadershipOptions
  const input = (label: string, name: string, placeholder: string, required = false, type = 'text') => <label className="growth-enquiry__field">{!['company', 'full_name', 'work_email', 'phone'].includes(name) && <span>{label}</span>}<input aria-label={label} name={name} placeholder={placeholder} required={required} type={type} /></label>
  const select = (label: string, name: string, options: string[], optional = false) => <GrowthDropdown label={label} name={name} options={options} optional={optional} />

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitState !== 'idle') return
    if (!selected.length) {
      setNotice('Please select at least one hiring category.')
      return
    }
    const form = event.currentTarget
    if (!form.reportValidity()) return
    const body = new FormData(form)
    body.set('kind', kind)
    selected.forEach(category => body.append('categories', category === 'Other +' ? otherRole.trim() : category))
    if (!founding) { body.set('confidential', String(body.has('confidential'))); body.set('role_title', selected.map(category => category === 'Other +' ? otherRole.trim() : category).join(', ')) }
    if (attachment) body.set('attachment', attachment)
    else body.delete('attachment')
    setNotice('')
    setError('')
    setSubmitState('sending')
    try {
      await api.submitHiringEnquiry(body)
      setSubmitState('sent')
      setNotice('Thank you. Your request has been received. Our team will follow up at your work email.')
    } catch (caught) {
      setSubmitState('idle')
      setError(caught instanceof Error ? caught.message : 'Your request could not be sent. Please try again.')
    }
  }

  return <form className={`growth-enquiry growth-enquiry--founding${!founding ? ' growth-enquiry--leadership' : ''}`} aria-label={founding ? 'Founding team enquiry' : 'Leadership enquiry'} onSubmit={submit}>
    {founding && <p className="growth-enquiry__step">Founding team</p>}
    <div className="growth-enquiry__heading"><h3>{founding ? "Let’s build your founding team." : 'Tell us about the leader you need.'}</h3><button type="button" onClick={onClose} aria-label="Close growth enquiry"><X size={11} aria-hidden="true" /></button></div>
    {<label className="growth-enquiry__upload growth-enquiry__upload--top"><span>Upload JD(s)</span><small>{attachment ? attachment.name : 'PDF or DOCX'}</small><input aria-label="Upload JD or notes" name="attachment" type="file" accept=".pdf,.docx" onChange={event => setAttachment(event.target.files?.[0] ?? null)} /></label>}
    <div className="growth-enquiry__fields">
      {input('Company', 'company', 'Company name', true)}{input('Your name', 'full_name', 'Your name', true)}
      {input('Work email', 'work_email', 'name@company.com', true, 'email')}
      {input('Phone / WhatsApp', 'phone', '+91', false, 'tel')}
      {founding && select('Your role', 'founder_role', ['Founder', 'Founding team', 'HR team', 'Leadership'])}
      {founding && select('Location', 'location', ['Bengaluru', 'Mumbai', 'Delhi NCR', 'Hyderabad', 'Pune', 'Remote — India', 'Other'])}
    </div>
    {founding && <h4>What are you building?</h4>}
    {founding && <textarea className="growth-enquiry__wide" aria-label="What are you building?" name="product" required placeholder="The product in a sentence or two. What problem, for whom?" rows={2} />}
    <h4>{founding ? 'Who do you need first?' : 'Which leader do you need?'}</h4>
    <fieldset aria-label={founding ? 'Who do you need first?' : 'Which leader do you need?'}><div className="growth-enquiry__pills">{options.map(option => <button type="button" key={option} aria-pressed={selected.includes(option)} onClick={() => { setSelected(values => values.includes(option) ? values.filter(value => value !== option) : [...values, option]); setNotice('') }}>{option}</button>)}{selected.includes('Other +') && <input aria-label="Other role" placeholder="Which role do you need?" value={otherRole} required maxLength={160} onChange={event => setOtherRole(event.target.value)} />}</div></fieldset>
    {!founding && <><h4>What needs to be fundamentally different 12 months after this person joins for you to call them an exceptional hire?</h4><textarea className="growth-enquiry__wide" aria-label="What needs to be fundamentally different in 12 months?" name="outcome" required rows={2} placeholder="Raise the bar, build a team, fix delivery, take on a new market…" /><label className="growth-enquiry__confidential"><span>Keep this search confidential<small>We won’t name your company to candidates until you say so.</small></span><input aria-label="Keep this search confidential" type="checkbox" role="switch" name="confidential" defaultChecked /></label></>}
    <div className="growth-enquiry__fields">
      
      
    </div>
    {notice && <p className="growth-enquiry__notice" role="status">{notice}</p>}
    {error && <p className="growth-enquiry__notice growth-enquiry__notice--error" role="alert">{error}</p>}
    <div className="growth-enquiry__actions"><button className="growth-enquiry__submit" type="submit" disabled={submitState !== 'idle'}>{submitState === 'sending' ? 'Sending…' : submitState === 'sent' ? 'Sent' : founding ? 'Build Your Founding Team' : 'Find Leadership'}{!founding && <ArrowRight size={14} aria-hidden="true" />}</button><small className="growth-enquiry__privacy">Confidential by default. Your details stay private.</small></div>
    <label className="growth-enquiry__legal"><input type="checkbox" required /><span>Your details are private. I agree to the <a href="/terms" target="_blank" rel="noopener noreferrer">Terms</a> and <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.</span></label>
  </form>
}
