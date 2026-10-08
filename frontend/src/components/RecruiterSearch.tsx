import { useRef, type FormEvent } from 'react'
import { ArrowRight, BriefcaseBusiness, Mic } from 'lucide-react'
import type { Search } from '../types'
import './recruiter-search.css'

type Props = {
  query: string
  setQuery: (query: string) => void
  search: Search | null
  answer: string
  setAnswer: (answer: string) => void
  submit: (event: FormEvent) => void
  clarify: (answer: string) => void
  busy: boolean
  error: string
  projectName?: string
  clearProject: () => void
  voiceListening: boolean
  startVoiceSearch: () => void
}

const suggestions = [
  ['0→1 backend builders', '0-to-1 backend builders with 4 years experience, remote okay'],
  ['Production ML engineers', 'Production machine learning engineers with 4 years experience, remote okay'],
  ['Founding engineers', 'Founding engineers with 5 years experience, remote okay'],
]

/** Presentation only: criteria, clarification and discovery remain owned by the API. */
export default function RecruiterSearch({ query, setQuery, search, answer, setAnswer, submit,
  clarify, busy, error, projectName, clearProject, voiceListening, startVoiceSearch }: Props) {
  const answerRef = useRef<HTMLInputElement>(null)
  const composerRef = useRef<HTMLInputElement>(null)
  return <div className="search-hero search-chat-home editorial-search">
    <h1>Who are we hiring today?</h1>
    {projectName && <div className="search-project-context"><BriefcaseBusiness size={14} aria-hidden="true" /> Searching inside <b>{projectName}</b><button onClick={clearProject}>Remove</button></div>}
    <form className="search-box chat-composer" onSubmit={submit} aria-label="Search for candidates" aria-busy={busy}>
      <input ref={composerRef} type="text" value={query} onChange={event => setQuery(event.target.value)}
        placeholder="Example: Backend engineers in Bengaluru, 4–7 yrs, Java, Kafka, 0-to-1"
        aria-label="Candidate search"
        onKeyDown={event => {
          if (event.key === 'Enter') {
            event.preventDefault()
            if (!event.nativeEvent.isComposing && query.trim() && !busy) event.currentTarget.form?.requestSubmit()
          }
        }} />
      <div className="composer-actions">
        <button type="button" className={`voice-search ${voiceListening ? 'listening' : ''}`} onClick={startVoiceSearch}
          aria-label={voiceListening ? 'Listening for search' : 'Search by voice'} aria-pressed={voiceListening} title="Search by voice"><Mic aria-hidden="true" /></button>
        <button className="search-enter-button" aria-label="Search talent" disabled={busy || !query.trim()}>
          <img src="/enter-logo.jpeg" alt="" />
        </button>
      </div>
    </form>
    {busy && <span className="sr-only" role="status">Searching…</span>}
    {!search && <div className="search-hints" aria-label="Search suggestions">
      {suggestions.map(([label, value]) => <button key={label} onClick={() => { setQuery(value); composerRef.current?.focus() }}>{label}</button>)}
    </div>}
    {search?.state === 'needs_clarification' && <div className="search-conversation" aria-live="polite">
      <div className="conversation-row recruiter-message"><div><small>You</small><p>{search.query}</p></div></div>
      <form className="conversation-row enter-message" key={`${search.id}:${search.follow_up_question}`} aria-label="Clarify your search"
        onSubmit={event => { event.preventDefault(); clarify(answer) }}>
        <div className="ai-mark" aria-hidden="true">e</div>
        <div><small>Enter</small><b>One detail before I search</b><p>{search.follow_up_question}</p>
          {search.follow_up_options.length > 0 && <div className="clarification-options">
            {search.follow_up_options.map(option => <button type="button" key={option}
              onClick={() => option === 'Let me type it' ? answerRef.current?.focus() : clarify(option)} disabled={busy}>{option}</button>)}
          </div>}
          <div className="clarification-input"><input ref={answerRef} value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Type a different answer" aria-label="Clarification answer" />
            <button className="primary" disabled={!answer.trim() || busy}>Continue <ArrowRight size={14} aria-hidden="true" /></button>
          </div>
        </div>
      </form>
    </div>}
    {error && <div className="error" role="alert">{error}</div>}
  </div>
}
