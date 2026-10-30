import { useState, type FormEvent } from 'react'
import { api } from '../api'

type GrowthKind = 'founding' | 'leadership'

const foundingOptions = ['Founding Engineer', 'Founding AI / ML', 'Early Technical Leader (CTO / Head of Eng)', 'Founding Designer']
const leadershipOptions = ['Engineering Leader', 'Product Leader', 'Functional Leader (Data, Design, GTM)']
const cashRanges = ['₹20–40L', '₹40–60L', '₹60–90L', '₹90L–1.2Cr', '₹1.2–2Cr', 'Let’s discuss']

export default function GrowthEnquiry({ kind, onClose }: { kind: GrowthKind; onClose: () => void }) {
  const founding = kind === 'founding'
  const [selected, setSelected] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [attachment, setAttachment] = useState<File | null>(null)
  const [submitState, setSubmitState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const options = founding ? foundingOptions : leadershipOptions
  const today = new Date()
  const minimumMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
  const input = (label: string, name: string, placeholder: string, required = false, type = 'text') => <input aria-label={label} name={name} placeholder={placeholder} required={required} type={type} />
  const select = (label: string, name: string, options: string[], optional = false) => <select aria-label={label} name={name} required={!optional} defaultValue=""><option value="" disabled>Choose {label.toLowerCase()}</option>{options.map(value => <option key={value} value={value}>{value}</option>)}</select>

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
    selected.forEach(category => body.append('categories', category))
    if (!founding) body.set('confidential', String(body.has('confidential')))
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

  return <form className="growth-enquiry" aria-label={founding ? 'Founding team enquiry' : 'Leadership enquiry'} onSubmit={submit}>
    <div className="growth-enquiry__heading"><h3>{founding ? 'Tell us about your founding team.' : 'Tell us about the leader you need.'}</h3><button type="button" onClick={onClose} aria-label="Close growth enquiry">×</button></div>
    <div className="growth-enquiry__fields">
      {input('Company', 'company', 'Company name', true)}{input('Your name', 'full_name', 'Full name', true)}
      {input('Work email', 'work_email', 'name@company.com', true, 'email')}
      {founding && select('Your role', 'founder_role', ['Founder', 'CEO', 'CTO', 'Other'])}
      {input('Phone / WhatsApp (optional)', 'phone', '+91', false, 'tel')}{input('Website or LinkedIn', 'website', 'company.com')}
    </div>
    {founding && <textarea className="growth-enquiry__wide" aria-label="What are you building?" name="product" required placeholder="What are you building? The product in a sentence or two." rows={2} />}
    <fieldset aria-label={founding ? 'Who do you need first?' : 'Which leader do you need?'}><div className="growth-enquiry__pills">{options.map(option => <button type="button" key={option} aria-pressed={selected.includes(option)} onClick={() => { setSelected(values => values.includes(option) ? values.filter(value => value !== option) : [...values, option]); setNotice('') }}>{option}</button>)}</div></fieldset>
    <div className="growth-enquiry__fields">
      {founding ? select('How many people', 'people_count', ['1', '2', '3', '4', '5', '6–10', '10+']) : select('Role title', 'role_title', ['VP Engineering', 'CTO', 'Head of Engineering', 'Chief Product Officer', 'Head of Product', 'Functional Head', 'Other'])}
      {founding && <label className="growth-enquiry__upload">Upload JD / notes ↑<input aria-label="Upload JD or notes" name="attachment" type="file" accept=".pdf,.docx,.txt" onChange={event => setAttachment(event.target.files?.[0] ?? null)} /></label>}
    </div>
    {!founding && <><textarea className="growth-enquiry__wide" aria-label="What needs to be fundamentally different in 12 months?" name="outcome" required rows={2} placeholder="What should be fundamentally different in 12 months?" /><label className="growth-enquiry__confidential"><span>Keep this search confidential<small>We won’t reveal your company to candidates until you say so.</small></span><input aria-label="Keep this search confidential" type="checkbox" name="confidential" defaultChecked /></label></>}
    <div className="growth-enquiry__fields">
      {select(founding ? 'Cash range (optional)' : 'Compensation (optional)', founding ? 'cash_range' : 'compensation', cashRanges, true)}
      {founding && select('Equity range (optional)', 'equity_range', ['0–0.5%', '0.5–1.5%', '1.5–3%', '3%+', 'Let’s discuss'], true)}
      {input(founding ? 'Location' : 'Location / mode', founding ? 'location' : 'location_mode', 'Bengaluru, Hybrid', true)}
      {founding && <input aria-label="Start by" name="start_month" type="month" min={minimumMonth} required />}
    </div>
    {notice && <p className="growth-enquiry__notice" role="status">{notice}</p>}
    {error && <p className="growth-enquiry__notice growth-enquiry__notice--error" role="alert">{error}</p>}
    <button className="growth-enquiry__submit" type="submit" disabled={submitState !== 'idle'}>{submitState === 'sending' ? 'Sending…' : submitState === 'sent' ? 'Sent' : founding ? 'Submit' : 'Find Leadership'}</button>
  </form>
}
