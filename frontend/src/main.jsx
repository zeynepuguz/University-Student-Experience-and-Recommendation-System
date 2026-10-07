import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import { Analytics } from '@vercel/analytics/react'
import './index.css'
import App from './App.jsx'
import { API_URL } from './api.js'
import { initMonitoring } from './monitoring.js'

initMonitoring(API_URL)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={<p>Bir şeyler ters gitti. Sayfayı yenilemeyi dene.</p>}
    >
      <App />
    </Sentry.ErrorBoundary>
    <Analytics />
  </StrictMode>,
)
