import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import SiteMotion from './components/SiteMotion'
import './styles.css'
import './components/platform-background.css'

createRoot(document.getElementById('root')!).render(<StrictMode><Suspense fallback={null}><App /></Suspense><SiteMotion /></StrictMode>)
