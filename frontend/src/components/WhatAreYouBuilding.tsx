import { useEffect, useId, useRef, useState } from 'react'
import { ArrowRight, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import useInlinePopover from './useInlinePopover'
import { listenForHiringSectionNavigation } from './hiringSectionNavigation'
import observeLandingReveal from './observeLandingReveal'
import HiringEnquiryDrawer, { type HiringEnquiry } from './HiringEnquiryDrawer'
import './what-are-you-building.css'

type TabId = 'hire' | 'team' | 'drive'

const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'hire', label: 'Hire Talent' },
  { id: 'team', label: 'Build My Team' },
  { id: 'drive', label: 'Conduct a Recruitment Drive' },
]

const roles = [
  'Staff Backend Engineer',
  'Senior Frontend Engineer',
  'Platform Engineer',
  'Machine Learning Engineer',
  'Engineering Manager',
]

const locations = ['Bengaluru', 'Mumbai', 'Delhi NCR', 'Hyderabad', 'Pune', 'Remote — India']
const teamDisciplines = ['Backend Engineering', 'Frontend Engineering', 'Platform Engineering', 'Data Engineering', 'Product Engineering']
const teamSizes = ['4 people', '6 people', '8 people', '10 people', '12 people']
const driveCounts = ['6', '8', '10', '12', '15', '20']
const driveRoles = ['Backend Engineers', 'Frontend Engineers', 'Platform Engineers', 'Data Engineers', 'Full-stack Engineers']

function localDay(value = new Date()) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function addDays(value: Date, days: number) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate() + days)
}

function dateKey(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function dateFromKey(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function formatDeadline(value: string) {
  const date = dateFromKey(value)
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long' })
    .format(date)
}

function fullDateLabel(value: Date) {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(value)
}

function clampDateKey(value: string, minimum: Date) {
  const date = dateFromKey(value)
  if (date < minimum) return dateKey(minimum)
  return dateKey(date)
}

function InlineListbox({ label, value, options, onChange }: {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const listboxId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  useInlinePopover(open, setOpen, triggerRef, listRef)
  const selectedIndex = Math.max(options.indexOf(value), 0)

  const focusOption = (index: number) => {
    window.requestAnimationFrame(() => {
      listRef.current?.querySelectorAll<HTMLElement>('[role="option"]')[index]?.focus()
    })
  }

  const openListbox = (index = selectedIndex) => {
    setOpen(true)
    focusOption(index)
  }

  const chooseOption = (option: string) => {
    onChange(option)
    setOpen(false)
    window.requestAnimationFrame(() => triggerRef.current?.focus())
  }

  return <div className="wb-inline-field wb-listbox" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <button
      ref={triggerRef}
      className="wb-listbox__trigger"
      type="button"
      aria-label={`${label}: ${value}`}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={listboxId}
      onClick={() => open ? setOpen(false) : openListbox()}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          openListbox(Math.min(selectedIndex + 1, options.length - 1))
        } else if (event.key === 'ArrowUp') {
          event.preventDefault()
          openListbox(Math.max(selectedIndex - 1, 0))
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault()
          openListbox(event.key === 'Home' ? 0 : options.length - 1)
        } else if (event.key === 'Escape') {
          setOpen(false)
        }
      }}
    >
      {value}
    </button>
    <ChevronDown size={14} aria-hidden="true" />
    <ul ref={listRef} id={listboxId} className="wb-listbox__menu" role="listbox" aria-label={label} hidden={!open}>
      {options.map((option, index) => <li
        key={option}
        role="option"
        aria-selected={option === value}
        tabIndex={option === value ? 0 : -1}
        onClick={() => chooseOption(option)}
        onKeyDown={event => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            const direction = event.key === 'ArrowDown' ? 1 : -1
            const nextIndex = (index + direction + options.length) % options.length
            focusOption(nextIndex)
          } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault()
            focusOption(event.key === 'Home' ? 0 : options.length - 1)
          } else if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            chooseOption(option)
          } else if (event.key === 'Escape') {
            event.preventDefault()
            setOpen(false)
            triggerRef.current?.focus()
          }
        }}
      >{option}</li>)}
    </ul>
  </div>
}

function InlineCalendar({ value, minimum, onChange }: {
  value: string
  minimum: Date
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const selected = dateFromKey(value)
    return new Date(selected.getFullYear(), selected.getMonth(), 1)
  })
  const calendarId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)
  useInlinePopover(open, setOpen, triggerRef, popupRef)
  const selectedDate = dateFromKey(value)
  const today = localDay()

  useEffect(() => {
    if (!open) return
    window.requestAnimationFrame(() => {
      gridRef.current?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus()
    })
  }, [open])

  const openCalendar = () => {
    const selected = dateFromKey(value)
    setVisibleMonth(new Date(selected.getFullYear(), selected.getMonth(), 1))
    setOpen(true)
  }

  const firstDay = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1)
  const monthEnd = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 0)
  const previousMonthEnd = addDays(firstDay, -1)
  const nextMonthStart = addDays(monthEnd, 1)
  const canGoPrevious = previousMonthEnd >= minimum
  const cells: Array<Date | null> = Array.from({ length: firstDay.getDay() }, () => null)
  for (let day = 1; day <= monthEnd.getDate(); day += 1) {
    cells.push(new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), day))
  }
  while (cells.length % 7) cells.push(null)

  const focusDate = (date: Date) => {
    date = dateFromKey(clampDateKey(dateKey(date), minimum))
    if (date.getMonth() !== visibleMonth.getMonth() || date.getFullYear() !== visibleMonth.getFullYear()) {
      setVisibleMonth(new Date(date.getFullYear(), date.getMonth(), 1))
    }
    window.requestAnimationFrame(() => {
      gridRef.current?.querySelector<HTMLButtonElement>(`[data-date="${dateKey(date)}"]`)?.focus()
    })
  }

  const selectDate = (date: Date) => {
    if (date < minimum) return
    onChange(dateKey(date))
    setOpen(false)
    window.requestAnimationFrame(() => triggerRef.current?.focus())
  }

  return <div className="wb-inline-field wb-calendar" onBlur={event => {
    // A month arrow can become disabled after navigation; that blur is not dismissal.
    if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <button
      ref={triggerRef}
      className="wb-calendar__trigger"
      type="button"
      aria-label={`Recruitment drive deadline: ${fullDateLabel(selectedDate)}`}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={calendarId}
      onClick={() => open ? setOpen(false) : openCalendar()}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          openCalendar()
        } else if (event.key === 'Escape') {
          setOpen(false)
        }
      }}
    >{formatDeadline(value)}</button>
    <ChevronDown size={14} aria-hidden="true" />
    <div
      ref={popupRef}
      id={calendarId}
      className="wb-calendar__popover"
      role="dialog"
      aria-modal="false"
      aria-label="Choose recruitment drive deadline"
      hidden={!open}
    >
      <div className="wb-calendar__header">
        <button type="button" aria-label="Previous month" disabled={!canGoPrevious} onClick={() => focusDate(previousMonthEnd)}><ChevronLeft size={17} aria-hidden="true" /></button>
        <strong aria-live="polite">{new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' }).format(visibleMonth)}</strong>
        <button type="button" aria-label="Next month" onClick={() => focusDate(nextMonthStart)}><ChevronRight size={17} aria-hidden="true" /></button>
      </div>
      <div className="wb-calendar__weekdays" aria-hidden="true">
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}
      </div>
      <div ref={gridRef} className="wb-calendar__grid" role="grid" aria-label={new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' }).format(visibleMonth)}>
        {cells.map((date, index) => date ? <button
          key={dateKey(date)}
          type="button"
          role="gridcell"
          data-date={dateKey(date)}
          aria-label={fullDateLabel(date)}
          aria-current={dateKey(date) === dateKey(today) ? 'date' : undefined}
          aria-selected={dateKey(date) === value}
          disabled={date < minimum}
          tabIndex={dateKey(date) === value ? 0 : -1}
          className={`${dateKey(date) === dateKey(today) ? 'is-today' : ''}${dateKey(date) === value ? ' is-selected' : ''}`}
          onClick={() => selectDate(date)}
          onKeyDown={event => {
            let target: Date
            if (event.key === 'ArrowRight') target = addDays(date, 1)
            else if (event.key === 'ArrowLeft') target = addDays(date, -1)
            else if (event.key === 'ArrowDown') target = addDays(date, 7)
            else if (event.key === 'ArrowUp') target = addDays(date, -7)
            else if (event.key === 'Home') target = addDays(date, -date.getDay())
            else if (event.key === 'End') target = addDays(date, 6 - date.getDay())
            else if (event.key === 'Escape') {
              event.preventDefault()
              setOpen(false)
              triggerRef.current?.focus()
              return
            } else return
            event.preventDefault()
            focusDate(target)
          }}
        >{date.getDate()}</button> : <span key={`blank-${index}`} aria-hidden="true" />)}
      </div>
      <p>From {fullDateLabel(minimum)} onwards</p>
    </div>
  </div>
}

export default function WhatAreYouBuilding() {
  const sectionRef = useRef<HTMLElement>(null)
  const [opener, setOpener] = useState<HTMLButtonElement | null>(null)
  const [enquiry, setEnquiry] = useState<HiringEnquiry | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('hire')
  const [hireRole, setHireRole] = useState(roles[1])
  const [teamLocation, setTeamLocation] = useState(locations[3])
  const [hireLocation, setHireLocation] = useState(locations[3])
  const [teamDiscipline, setTeamDiscipline] = useState(teamDisciplines[0])
  const [teamSize, setTeamSize] = useState(teamSizes[1])
  const [driveCount] = useState(driveCounts[3])
  const [driveRole, setDriveRole] = useState(driveRoles[0])
  const [driveLocation, setDriveLocation] = useState(locations[0])
  const [today, setToday] = useState(() => localDay())
  const [deadline, setDeadline] = useState(() => dateKey(addDays(localDay(), 14)))
  const safeDeadline = clampDateKey(deadline, today)

  useEffect(() => {
    if (sectionRef.current) return observeLandingReveal(sectionRef.current, 0.15)
  }, [])

  useEffect(() => listenForHiringSectionNavigation(({ tab, role }) => {
    setActiveTab(tab)
    if (role && roles.includes(role)) setHireRole(role)
  }), [])

  useEffect(() => {
    const nextDay = addDays(today, 1)
    const refreshAtMidnight = window.setTimeout(() => setToday(localDay()), Math.max(1000, nextDay.getTime() - Date.now() + 100))
    return () => window.clearTimeout(refreshAtMidnight)
  }, [today])

  useEffect(() => {
    const refresh = () => setToday(current => dateKey(current) === dateKey(localDay()) ? current : localDay())
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [])

  const selectTab = (tab: TabId) => {
    setActiveTab(tab)
  }

  return <section ref={sectionRef} id="what-building-section" className="what-building" aria-labelledby="what-building-title">
    <div className="what-building__art" aria-hidden="true">

    </div>
    <div className="what-building__inner">
      <p className="what-building__eyebrow">Start here</p>
      <h2 id="what-building-title">What are you building next?</h2>
      <p className="what-building__intro">Tell us what you're building. We'll help you find the people to build it.</p>

      <div className="what-building__tabs" role="tablist" aria-label="Hiring goal">
        {tabs.map((tab, index) => <button
          key={tab.id}
          id={`building-tab-${tab.id}`}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`building-panel-${tab.id}`}
          tabIndex={activeTab === tab.id ? 0 : -1}
          onClick={() => selectTab(tab.id)}
          onKeyDown={event => {
            let nextIndex: number
            if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length
            else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length
            else if (event.key === 'Home') nextIndex = 0
            else if (event.key === 'End') nextIndex = tabs.length - 1
            else return
            event.preventDefault()
            selectTab(tabs[nextIndex].id)
            event.currentTarget.parentElement
              ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[nextIndex]
              ?.focus()
          }}
        >{tab.label}</button>)}
      </div>

      <div
        className="what-building__panel"
        id="building-panel-hire"
        role="tabpanel"
        aria-labelledby="building-tab-hire"
        hidden={activeTab !== 'hire'}
      >
        <div className="what-building__sentence">
          I'm looking for a <InlineListbox label="Role to hire" value={hireRole} options={roles} onChange={setHireRole} /> in <InlineListbox label="Hiring location" value={hireLocation} options={locations} onChange={setHireLocation} />
        </div>
        <button className="what-building__cta" type="button" onClick={event => { setOpener(event.currentTarget); setEnquiry({ kind: 'hire', role: hireRole, location: hireLocation, headcount: 1 }) }}>Find Talent <ArrowRight size={16} aria-hidden="true" /></button>
      </div>

      <div
        className="what-building__panel"
        id="building-panel-team"
        role="tabpanel"
        aria-labelledby="building-tab-team"
        hidden={activeTab !== 'team'}
      >
        <div className="what-building__sentence">
          I'm building a <InlineListbox label="Team discipline" value={teamDiscipline} options={teamDisciplines} onChange={setTeamDiscipline} /> team of <InlineListbox label="Team size" value={teamSize} options={teamSizes} onChange={setTeamSize} /> in <InlineListbox label="Team location" value={teamLocation} options={locations} onChange={setTeamLocation} />
        </div>
        <button className="what-building__cta" type="button" onClick={event => { setOpener(event.currentTarget); setEnquiry({ kind: 'team', location: teamLocation, teamFocus: teamDiscipline, headcount: Number.parseInt(teamSize, 10) }) }}>Build My Team <ArrowRight size={16} aria-hidden="true" /></button>
      </div>

      <div
        className="what-building__panel"
        id="building-panel-drive"
        role="tabpanel"
        aria-labelledby="building-tab-drive"
        hidden={activeTab !== 'drive'}
      >
        <div className="what-building__sentence what-building__sentence--drive">
          I am looking for <InlineListbox label="Role for recruitment drive" value={driveRole} options={driveRoles} onChange={setDriveRole} /> in <InlineListbox label="Recruitment drive location" value={driveLocation} options={locations} onChange={setDriveLocation} /> by <InlineCalendar value={safeDeadline} minimum={today} onChange={setDeadline} />
        </div>
        <button className="what-building__cta" type="button" onClick={event => { setOpener(event.currentTarget); setEnquiry({ kind: 'drive', role: driveRole, location: driveLocation, headcount: Number(driveCount), deadline: safeDeadline }) }}>Plan My Drive <ArrowRight size={16} aria-hidden="true" /></button>
      </div>

    </div>
    {enquiry && <HiringEnquiryDrawer enquiry={enquiry} minimumDate={dateKey(today)} opener={opener} onClose={() => setEnquiry(null)} />}
  </section>
}
