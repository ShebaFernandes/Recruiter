import { Search, Folder, Bell } from 'lucide-react'
import RecruiterSearch from './RecruiterSearch'

const noop = () => {}

/** Read-only public preview of the real empty search screen. No account data or API calls. */
export default function LandingProductPreview() {
  return <figure className="ce-product-preview" aria-label="Preview of ENTER's recruiter search interface">
    <figcaption className="ce-window-bar"><span className="ce-window-dots" aria-hidden="true"><i /><i /><i /></span><span>ENTER · Talent Platform</span><span>Product preview</span></figcaption>
    <div className="ce-preview-interface" inert aria-hidden="true">
      <div className="ce-preview-top"><img src="/enter-wordmark.svg" alt="" /><span>Talent Platform</span><Bell size={16} /></div>
      <div className="ce-preview-body">
        <aside><span><Search size={17} />Search</span><span><Folder size={17} />Projects</span></aside>
        <div className="recruiter-search-mode"><RecruiterSearch query="" setQuery={noop} search={null} answer="" setAnswer={noop} submit={event => event.preventDefault()} clarify={noop} busy={false} error="" clearProject={noop} voiceListening={false} startVoiceSearch={noop} /></div>
      </div>
    </div>
  </figure>
}
