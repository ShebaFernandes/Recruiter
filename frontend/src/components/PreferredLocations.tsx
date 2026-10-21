import { useEffect, useId, useRef, useState } from 'react'

const cities = ['Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad', 'Pune', 'Chennai', 'Gurugram', 'Noida', 'Kolkata']
const normalize = (value: string) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase()

export default function PreferredLocations({ initial, changed }: { initial: string[]; changed: () => void }) {
  const [selected, setSelected] = useState(initial)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const id = useId()
  const listRef = useRef<HTMLUListElement>(null)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(blurTimer.current), [])
  useEffect(() => { listRef.current?.querySelector('[aria-selected=true]')?.scrollIntoView?.({ block: 'nearest' }) }, [active])
  const matches = cities.filter(city => normalize(city).includes(normalize(query)) && !selected.some(value => normalize(value) === normalize(city)))
  const custom = query.trim().replace(/\s+/g, ' ')
  const options = custom && ![...cities, ...selected].some(value => normalize(value) === normalize(custom)) ? [...matches, custom] : matches
  function add(value: string) {
    if (!selected.some(item => normalize(item) === normalize(value))) { setSelected([...selected, value]); changed() }
    setQuery(''); setActive(0); setOpen(false)
  }
  // Let the next control receive its click before collapsing the in-flow list.
  return <div className="cp-locations" onFocusCapture={() => clearTimeout(blurTimer.current)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) blurTimer.current = setTimeout(() => setOpen(false), 150) }}>
    <label htmlFor={id}>Preferred locations</label>
    <div className="cp-location-chips">{selected.map((value, index) => <span key={`${value}-${index}`}>{value}<button type="button" aria-label={`Remove ${value}`} onClick={() => { setSelected(selected.filter((_, i) => i !== index)); changed() }}>×</button><input type="hidden" name="locations" value={value} /></span>)}</div>
    <input ref={node => { node?.setCustomValidity(query.trim() ? 'Select a location or clear your search before saving.' : '') }} id={id} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-options`} aria-activedescendant={open && options[active] ? `${id}-${active}` : undefined} value={query} placeholder="Search or add a location" onFocus={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setActive(0); setOpen(true) }} onKeyDown={event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive(index => Math.max(0, Math.min(options.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))) }
      if (event.key === 'Enter') { event.preventDefault(); if (options[active]) add(options[active]); else if (selected.some(value => normalize(value) === normalize(query))) { setQuery(''); setOpen(false) } }
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
    }} />
    {open && <ul ref={listRef} id={`${id}-options`} role="listbox" aria-label="Location suggestions">{options.map((value, index) => <li id={`${id}-${index}`} key={value} role="option" aria-selected={index === active} onPointerDown={event => event.preventDefault()} onClick={() => add(value)}>{cities.includes(value) ? value : `Add “${value}”`}</li>)}{!options.length && <li role="presentation">No additional matches</li>}</ul>}
    <small>Locations save automatically. Type to add another.</small>
  </div>
}
