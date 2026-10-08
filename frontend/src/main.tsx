import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './components/recruiter-results.css'
import './components/recruiter-workspace.css'
import './components/candidate-platform.css'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
