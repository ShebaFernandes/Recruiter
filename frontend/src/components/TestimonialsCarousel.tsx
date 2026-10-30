import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import { Marquee } from './ui/marquee'
import { MarqueeCard } from './ui/marquee-card'
import './testimonials-carousel.css'

export type Testimonial = { id: string; excerpt: string; paragraphs: string[]; name: string; attribution: string }

const testimonials: Testimonial[] = [
  {
    id: 'steve-francis',
    excerpt: 'What sets Dikshita & team apart is ownership.',
    name: 'Steve Francis',
    attribution: 'VP HR (ex-Practo, Licious)',
    paragraphs: [
      "I've worked with Enter Recruitment, across the last 5 yrs in my corporate journey leading HR teams & my Fractional HR business services.",
      "What sets Dikshita & team apart is ownership. She doesn't wait for job descriptions to land in her inbox, she invests time in understanding the business, the culture, and what a great hire actually looks like. The result is fewer CVs, better conversations, faster closes.",
      "For any startup or growth-stage company building a team that matters, Enter Recruitment is the absolutely the go to partner I'd recommend.",
    ],
  },
  {
    id: 'drushya-shetty',
    excerpt: 'This understanding translated into a strong pipeline of candidates who genuinely fit the bill.',
    name: 'Drushya Shetty',
    attribution: 'CRED',
    paragraphs: [
      'The team at Enter did a fabulous job of understanding my requirements, pain points, and ideal candidate profile. This understanding translated into a strong pipeline of candidates who genuinely fit the bill.',
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
    attribution: 'Talent Acquisition Specialist',
    paragraphs: [
      'It has been a pleasure working with the team at ENTER. We truly appreciate your responsiveness and the quality of support you have provided throughout our hiring process. Your ability to maintain a strong pace of placements without compromising on quality has been especially valuable.',
      'While some roles were particularly challenging to fill due to the level of scrutiny involved, ENTER’s commitment, persistence, and enthusiasm consistently stood out. Despite the difficulties, your team remained dedicated to finding the right fit.',
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
      <p className="testimonials-carousel__eyebrow">FROM THE PEOPLE WE BUILD WITH</p>
      <h2 id="testimonials-heading">Don’t take our word for it, here’s what our clients have to say.</h2>
    </div>
    <Marquee className="testimonials-carousel__viewport" pauseOnHover speed="slow" aria-label="Client testimonials">
      {testimonials.map(testimonial => <MarqueeCard
        key={testimonial.id}
        name={testimonial.name}
        role={testimonial.attribution}
        paragraphs={testimonial.paragraphs}
      />)}
    </Marquee>
  </section>
}
