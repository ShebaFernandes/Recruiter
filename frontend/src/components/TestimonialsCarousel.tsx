import testimonialLogo3 from '../assets/landing/logos/airtel.png'
import testimonialLogo2 from '../assets/landing/logos/lila-supplied.png'
import testimonialLogo1 from '../assets/landing/logos/parspec.png'
import testimonialLogo0 from '../assets/landing/logos/anthriq.png'
import { validateWorkEmailInput } from '../workEmail'
import mobikwikLogo from '../../..//design-references/prepared/trusted-by-review/assets/expanded/mobikwik.svg'
import doqfyLogo from '../../../design-references/prepared/trusted-by-review/assets/doqfy-official.svg'
import { previewCompanies } from './company-preview/companies'
import HiringEnquiryDrawer from './DeferredHiringEnquiryDrawer'
import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef, useState } from 'react'
import { Marquee } from './ui/marquee'
import { MarqueeCard } from './ui/marquee-card'
import './testimonials-carousel.css'

export type Testimonial = { id: string; excerpt: string; paragraphs: string[]; name: string; attribution: string; company?: string; videoUrl?: string }

const testimonials: Testimonial[] = [
  {
    id: 'alisha-tahasildar',
    name: 'Alisha Tahasildar',
    attribution: 'HR · Anthriq',
    company: 'Anthriq',
    excerpt: 'They helped us close a very critical role.',
    paragraphs: ['It’s been great working with ENTER. They helped us close a very critical role, and what stood out was that they hadn’t worked on a role like this before, yet still delivered. They were communicative and supportive throughout. I’d absolutely recommend them without hesitation.'],
  },
  {
    id: 'githin-joseph',
    excerpt: 'They act like an extension of the in-house recruitment team.',
    name: 'Githin Joseph',
    attribution: 'Sr. TA Partner, Nanonets',
    paragraphs: [
      "I've worked with ENTER at both MPL and Mayhem Studios. They act like an extension of the in-house recruitment team and are very particular about quality. They are quick to understand the brief, and they also help shape the job brief and advise on the talent pool.",
      "Dikshita is lovely to work with. They're the best partners if you want to build your team from the ground up or if you are scaling your team.",
      "They understand your brief, help sharpen it, and guide you on where the right talent is. They have a good understanding of the talent market.",
    ],
  },
  {
    id: 'steve-francis',
    excerpt: 'What sets Dikshita & team apart is ownership.',
    name: 'Steve Francis',
    attribution: 'VP HR (ex-Practo, Licious)',
    paragraphs: [
      "I've worked with enter Recruitment, across the last 5 yrs in my corporate journey leading HR teams & my Fractional HR business services.",
      "What sets Dikshita & team apart is ownership. She doesn't wait for job descriptions to land in her inbox, she invests time in understanding the business, the culture, and what a great hire actually looks like. The result is fewer CVs, better conversations, faster closes.",
      "For any startup or growth-stage company building a team that matters, enter Recruitment is the absolutely the go to partner I'd recommend.",
    ],
  },
  {
    id: 'drushya-shetty',
    excerpt: 'This understanding translated into a strong pipeline of candidates who genuinely fit the bill.',
    name: 'Drushya Shetty',
    attribution: 'Lead Talent Partner · CRED',
    paragraphs: [
      'The team at enter did a fabulous job of understanding my requirements, pain points, and ideal candidate profile. This understanding translated into a strong pipeline of candidates who genuinely fit the bill.',
      'I thoroughly enjoyed working with the team and Deekshitha, the founder. They were reliable, understood what I was looking for, and delivered quality results. Definitely a team I would recommend to anyone looking for a dependable recruitment partner!',
    ],
  },
  {
    id: 'divya-v',
    excerpt: 'We appreciate your support, coordination, and efforts in sharing relevant candidate profiles.',
    name: 'Divya V',
    attribution: 'Human Resources · DOQFY',
    paragraphs: [
      'It has been a good experience working with your team for our recruitment requirements. We appreciate your support, coordination, and efforts in sharing relevant candidate profiles and assisting us throughout the recruitment process.',
      'Thank you for your continued support.',
      'We look forward to maintaining a good professional association and working together on our future hiring requirements.',
    ],
  },
  {
    id: 'prachi-sharma',
    excerpt: 'Your ability to maintain a strong pace of placements without compromising on quality has been especially valuable.',
    name: 'Prachi Sharma',
    attribution: 'Talent Acquisition Specialist · Parspec',
    paragraphs: [
      'While some roles were particularly challenging to fill due to the level of scrutiny involved, ENTER’s commitment, persistence, and enthusiasm consistently stood out. Despite the difficulties, your team remained dedicated to finding the right fit. It has been a pleasure working with the team at ENTER. We truly appreciate your responsiveness and the quality of support you have provided throughout our hiring process. Your ability to maintain a strong pace of placements without compromising on quality has been especially valuable.',
    ],
  },
  { id:'nitika-thukral', name:'Nitika Thukral', attribution:'Senior Talent Analyst · MobiKwik', company:'MobiKwik', excerpt:'A valued extension of our Information Technology team.', paragraphs:["Enter has proven themselves as a valuable tech hiring partner to Mobikwik diverse hiring process. They go extra mile to consistently provide highly qualified candidates. Their proven, personalised process understands our culture and requirements and has resulted in outstanding hires for us. We are very pleased to consider them a valued extension of our Information Technology team."] },
  { id:'joseph-kim', name:'Joseph Kim', attribution:'CEO · LILA GAMES', company:'LILA GAMES', excerpt:'Enter has delivered!', videoUrl:'https://www.dropbox.com/s/gbw6at5nmsptl9x/joseph_kim-2021-8-27__18-7-11.mp4?dl=0', paragraphs:["Enter has been an incredible resource for us to help source very high quality candidates. We have a very high bar for candidates and Enter has delivered! Dikshita is one of the most effective recruiters I have ever worked with and the thoroughness of her work is really great. We have had a fantastic experience and we hope to work with ENTER for as long as we can."] },
  { id:'alka-ladhani', name:'Alka Ladhani', attribution:'Head HR · Airtel', company:'Airtel', excerpt:'The most screened and relevant profiles.', paragraphs:["We have received the most screened and relevant profiles from ENTER for our Engineering team."] },

]

export default function TestimonialsCarousel() {
  const sectionRef = useRef<HTMLElement>(null)
  const startRef = useRef<HTMLButtonElement>(null)
  const [email, setEmail] = useState('')
  const [enquiryOpen, setEnquiryOpen] = useState(false)
  const [opener, setOpener] = useState<HTMLButtonElement | null>(null)
  const today = new Date()
  const minimumDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.18)
  }, [])

  return <section ref={sectionRef} className="testimonials-carousel" aria-labelledby="testimonials-heading">
    <div className="testimonials-carousel__intro">
      <p className="testimonials-carousel__eyebrow">TESTIMONIALS</p>
      <h2 id="testimonials-heading">Don’t take our word for it.</h2>
      <p className="testimonials-carousel__subtitle">Hear from the teams we’ve built with.</p>
    </div>
    <Marquee className="testimonials-carousel__viewport" speed="normal" aria-label="Client testimonials">
      {testimonials.map(testimonial => <MarqueeCard
        key={testimonial.id}
        name={testimonial.name}
        role={testimonial.attribution}
        paragraphs={testimonial.paragraphs}
        company={testimonial.company ?? ({'githin-joseph':'Nanonets','steve-francis':'Practo','drushya-shetty':'CRED','divya-v':'DOQFY','prachi-sharma':'Parspec'}[testimonial.id])}
        logo={({ 'alisha-tahasildar':testimonialLogo0,'prachi-sharma':testimonialLogo1,'nitika-thukral':mobikwikLogo,'divya-v':doqfyLogo,'joseph-kim':testimonialLogo2,'alka-ladhani':testimonialLogo3}[testimonial.id]) ?? previewCompanies.find(company => testimonial.attribution.toLowerCase().includes(company.name.toLowerCase()))?.logo}
        videoUrl={testimonial.videoUrl}
      />)}
    </Marquee>
    <div className="testimonials-carousel__start">
      <h3>Build the team that takes you further.</h3>
      <p>From your next critical hire to the team that takes you to the next stage, start with ENTER.</p>
      <form className="testimonials-carousel__email" aria-label="Start building your team" onSubmit={event => { event.preventDefault(); setOpener(startRef.current); setEnquiryOpen(true) }}>
        <input type="email" onInput={event => validateWorkEmailInput(event.currentTarget)} name="work_email" aria-label="Work email" autoComplete="email" placeholder="Enter your work email" required value={email} onChange={event => setEmail(event.target.value)} />
        <button ref={startRef} type="submit">Get Started </button>
      </form>
    </div>
    {enquiryOpen && <HiringEnquiryDrawer enquiry={{ kind: 'hire', headcount: 1, showStats: true, workEmail: email.trim() }} minimumDate={minimumDate} opener={opener} onClose={() => setEnquiryOpen(false)} />}
  </section>
}
