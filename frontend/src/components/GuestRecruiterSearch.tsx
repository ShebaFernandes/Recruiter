import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import type { GuestSearch } from '../types'
import RecruiterSearch from './RecruiterSearch'
import './guest-search.css'

type Recognition = {
  lang: string; interimResults: boolean; start: () => void; abort: () => void
  onresult: ((event: { results: { 0: { 0: { transcript: string } } } }) => void) | null
  onerror: (() => void) | null; onend: (() => void) | null
}

const labels: Record<string, string> = {
  role: 'Role', skills: 'Skills', min_experience: 'Minimum experience (years)',
  max_experience: 'Maximum experience (years)', location: 'Location',
  notice_period_days: 'Maximum notice (days)', max_salary_lpa: 'Maximum salary (LPA)',
  employment_type: 'Employment type', work_preferences: 'Work preferences',
  remote_ok: 'Open to remote candidates',
}

/** Guest view never mounts RecruiterPortal or requests candidate/workspace APIs. */
export default function GuestRecruiterSearch({ home, workspace }: { home: () => void; workspace: () => void }) {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState<GuestSearch | null>(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [listening, setListening] = useState(false)
  const inFlight = useRef(false)
  const recognition = useRef<Recognition | null>(null)
  const completion = useRef<HTMLHeadingElement>(null)
  useEffect(() => () => {
    if (recognition.current) {
      recognition.current.onend = null
      recognition.current.onerror = null
      recognition.current.onresult = null
      recognition.current.abort()
    }
  }, [])
  useEffect(() => { if (search?.state === 'complete') completion.current?.focus() }, [search])

  async function run(action: () => Promise<GuestSearch>) {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true); setError('')
    try { setSearch(await action()); setAnswer('') }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Search could not be completed. Please try again.') }
    finally { inFlight.current = false; setBusy(false) }
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    if (query.length > 2000) { setError('Please keep your hiring request under 2,000 characters.'); return }
    void run(() => api.guestSearch(query))
  }
  function clarify(value: string) {
    if (!search || !value.trim()) return
    if (value.length > 500) { setError('Please keep your answer under 500 characters.'); return }
    void run(() => api.guestAnswer(search.token, value))
  }
  function startVoiceSearch() {
    if (listening) { recognition.current?.abort(); return }
    const browser = window as typeof window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }
    const Constructor = browser.SpeechRecognition || browser.webkitSpeechRecognition
    if (!Constructor) { setError('Voice search is not supported in this browser. Please type your search.'); return }
    const speech = new Constructor()
    recognition.current = speech
    speech.lang = 'en-IN'; speech.interimResults = false
    speech.onresult = event => { setQuery(event.results[0][0].transcript); setError('') }
    speech.onerror = () => { setError('Microphone unavailable. Please type your search.'); setListening(false) }
    speech.onend = () => setListening(false)
    try { speech.start(); setListening(true) } catch { speech.onerror() }
  }
  return <main className="recruiter-search-mode guest-search">
    <header className="guest-search-header">
      <button onClick={home} aria-label="Back to Enter"><img src="/enter-wordmark.svg" alt="Enter" width="98" height="42" /></button>
      <nav aria-label="Guest recruiter navigation">
        <button disabled={busy} onClick={() => { setSearch(null); setQuery(''); setAnswer(''); setError('') }}>New search</button>
        <button onClick={workspace} title="Sign in to access private candidate profiles and saved recruiter actions">Recruiter workspace</button>
      </nav>
    </header>
    <RecruiterSearch query={query} setQuery={setQuery} search={search} answer={answer} setAnswer={setAnswer}
      submit={submit} clarify={clarify} busy={busy} error={error} clearProject={() => undefined}
      voiceListening={listening} startVoiceSearch={startVoiceSearch} />
    {search?.state === 'complete' && <section className="guest-search-brief" aria-labelledby="guest-brief-title">
      <h2 id="guest-brief-title" ref={completion} tabIndex={-1}>Your search brief is ready</h2>
      <dl>{Object.entries(search.criteria).filter(([key, value]) => labels[key] && value !== null && value !== '' && value !== false && (!Array.isArray(value) || value.length > 0)).map(([key, value]) =>
        <div key={key}><dt>{labels[key]}</dt><dd>{Array.isArray(value) ? value.join(', ') : value === true ? 'Yes' : String(value)}</dd></div>)}</dl>
      <p>Candidate profiles, resumes, contact details, and saved recruiter actions require an authorized recruiter account.</p>
      <button className="primary" onClick={workspace}>Open protected recruiter workspace</button>
    </section>}
    <p className="guest-search-notice">No login needed to describe your hiring needs. Candidate information stays private. Please don’t include personal or confidential information in your request.</p>
  </main>
}
