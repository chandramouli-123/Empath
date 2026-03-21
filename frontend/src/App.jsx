import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import QuickStartPage from './pages/QuickStartPage'
import SessionPage from './pages/SessionPage'
import ReportPage from './pages/ReportPage'
import QuizPage from './pages/QuizPage'
import ReportLookupPage from './pages/ReportLookupPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/start" element={<QuickStartPage />} />
      <Route path="/session" element={<SessionPage />} />
      <Route path="/report/:sessionId" element={<ReportPage />} />
      <Route path="/quiz/:sessionId" element={<QuizPage />} />
      <Route path="/report-lookup" element={<ReportLookupPage />} />
    </Routes>
  )
}
