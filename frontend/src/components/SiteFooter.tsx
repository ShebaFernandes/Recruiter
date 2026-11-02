import EnterLogo from './EnterLogo'
import './site-footer.css'

export default function SiteFooter() {
  return <div className="site-footer-surface"><footer className="site-footer" aria-label="Enter footer">
    <a className="site-footer-brand" href="/" aria-label="Enter home"><EnterLogo /></a>
    <p className="site-footer-tagline">Humanity. Integrity and Possibility.</p>
    <nav className="site-footer-links" aria-label="Footer navigation">
      <a href="/opportunities">Opportunities</a>
      <a href="/careers">Careers</a>
      <a href="mailto:sheba@enterrecruitment.com">Contact</a>
      <a href="https://www.linkedin.com/company/enterrecruitment/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
    </nav>
  </footer></div>
}
