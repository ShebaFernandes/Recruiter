import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import { Marquee } from './ui/marquee'
import { MarqueeCard } from './ui/marquee-card'
import './testimonials-carousel.css'

export type Testimonial = { id: string; excerpt: string; paragraphs: string[]; name: string; attribution: string }

const testimonials: Testimonial[] = [
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
    attribution: 'CRED',
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
      'It has been a pleasure working with the team at enter. We truly appreciate your responsiveness and the quality of support you have provided throughout our hiring process. Your ability to maintain a strong pace of placements without compromising on quality has been especially valuable.',
      'While some roles were particularly challenging to fill due to the level of scrutiny involved, enter’s commitment, persistence, and enthusiasm consistently stood out. Despite the difficulties, your team remained dedicated to finding the right fit.',
      'We sincerely appreciate you and your team of professionals for your continued support.',
      'Looking forward to our continued partnership.',
    ],
  },
]

export default function TestimonialsCarousel() {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.18)
  }, [])

  return <section ref={sectionRef} className="testimonials-carousel" aria-labelledby="testimonials-heading">
    <div className="testimonials-carousel__intro">
      <p className="testimonials-carousel__eyebrow">TESTIMONIALS</p>
      <h2 id="testimonials-heading">Don’t take our word for it</h2>
    </div>
    <Marquee className="testimonials-carousel__viewport" pauseOnHover speed="fast" aria-label="Client testimonials">
      {testimonials.map(testimonial => <MarqueeCard
        key={testimonial.id}
        name={testimonial.name}
        role={testimonial.attribution}
        paragraphs={testimonial.paragraphs}
      />)}
    </Marquee>
  </section>
}
