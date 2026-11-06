import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import Timeline from '../src/components/CandidateCareerTimeline'
import type { WorkExperience } from '../src/types'
import '../src/styles.css'
import '../src/components/candidate-experience.css'
import '../src/components/candidate-theme.css'
const root = document.getElementById('root')!
export function Replay() {
  const [items, setItems] = useState<WorkExperience[]>(JSON.parse(root.dataset.items!))
  return <main className="candidate-experience" style={{ padding: 20 }}><Timeline items={items} saveRole={async (id, patch) => {
    setItems(rows => rows.map(row => row.id === id ? { ...row, ...patch } : row))
    return true
  }} /></main>
}
createRoot(root).render(<Replay />)
