import { createContext, useContext, useState } from 'react'

const SessionContext = createContext(null)

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null)
  const [studentId, setStudentId] = useState('student_001')
  const [studentName, setStudentName] = useState('')
  const [topic, setTopic] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [isActive, setIsActive] = useState(false)
  const [feedbackAdjustments, setFeedbackAdjustments] = useState(null)

  function startSession(id, name, topicVal, url, sId = 'student_001', adjustments = null) {
    setSessionId(id)
    setStudentName(name)
    setStudentId(sId)
    setTopic(topicVal)
    setVideoUrl(url)
    setIsActive(true)
    setFeedbackAdjustments(adjustments)
  }

  function clearSession() {
    setSessionId(null)
    setStudentName('')
    setTopic('')
    setVideoUrl('')
    setIsActive(false)
    setFeedbackAdjustments(null)
  }

  return (
    <SessionContext.Provider value={{
      sessionId, studentId, studentName, topic, videoUrl, isActive,
      feedbackAdjustments,
      startSession, clearSession,
    }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
