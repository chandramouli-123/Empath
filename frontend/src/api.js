import axios from 'axios'

const BASE = 'http://localhost:8000/api'

export async function checkHealth() {
  const { data } = await axios.get(`${BASE}/health`)
  return data  // { models_ready: bool }
}

export async function getVideoInfo(videoUrl) {
  const { data } = await axios.get(`${BASE}/video-info`, { params: { url: videoUrl } })
  return data  // { title, description, chapters, duration, channel }
}

export async function startSession(studentId, videoId, topic, videoUrl = '') {
  const { data } = await axios.post(`${BASE}/start-session`, null, {
    params: { student_id: studentId, video_id: videoId, topic, video_url: videoUrl }
  })
  return data  // { session_id, feedback_adjustments }
}

export async function analyzeEmotion(imageBlob) {
  const form = new FormData()
  form.append('file', imageBlob, 'frame.jpg')
  const { data } = await axios.post(`${BASE}/analyze-emotion`, form)
  return data  // { emotion, confidence, raw_label, phone_detected, distractions }
}

export async function sendBehaviorEvent(sessionId, timestampSeconds, eventType) {
  await axios.post(`${BASE}/behavior-event`, {
    session_id: sessionId,
    timestamp_seconds: timestampSeconds,
    event_type: eventType,
  })
}

export async function sendTabSwitch(sessionId, timestampSeconds, isVisible) {
  await axios.post(`${BASE}/tab-switch`, {
    session_id: sessionId,
    timestamp_seconds: timestampSeconds,
    is_visible: isVisible,
  })
}

export async function computeScore(sessionId, emotion, confidence, recentEvents, timestampSeconds, isDistracted = false, distractionReasons = []) {
  const { data } = await axios.post(`${BASE}/compute-score`, {
    session_id: sessionId,
    emotion,
    confidence,
    recent_events: recentEvents,
    timestamp_seconds: timestampSeconds,
    is_distracted: isDistracted,
    distraction_reasons: distractionReasons,
  })
  return data  // { seqi_score, focus_score, be, es, id, rr, engagement_state, trend_slope, emotion, is_distracted }
}

export async function getSuggestion(sessionId, engagementState, topic, timestampSeconds, behavioralSummary = null, seqiTrend = 0) {
  const { data } = await axios.post(`${BASE}/get-suggestion`, {
    session_id: sessionId,
    engagement_state: engagementState,
    topic,
    timestamp_seconds: timestampSeconds,
    behavioral_summary: behavioralSummary,
    seqi_trend: seqiTrend,
  })
  return data  // { suggestion, action, category }
}

export async function getSessionReport(sessionId) {
  const { data } = await axios.get(`${BASE}/session-report/${sessionId}`)
  return data
}

export async function getSessionAnalytics(sessionId) {
  const { data } = await axios.get(`${BASE}/session-analytics/${sessionId}`)
  return data
}

export async function getSessionTimeline(sessionId) {
  const { data } = await axios.get(`${BASE}/session-timeline/${sessionId}`)
  return data
}

export async function endSession(sessionId) {
  const { data } = await axios.post(`${BASE}/end-session/${sessionId}`)
  return data  // { ended, final_seqi }
}

export async function generateQuiz(sessionId) {
  const { data } = await axios.post(`${BASE}/quiz/generate/${sessionId}`)
  return data  // { questions, session_id }
}

export async function submitQuiz(sessionId, studentId, answers) {
  const { data } = await axios.post(`${BASE}/quiz/submit/${sessionId}`, {
    session_id: sessionId,
    student_id: studentId,
    answers,
  })
  return data  // { scores, total_score, session_id }
}

export async function getFeedback(studentId) {
  const { data } = await axios.get(`${BASE}/feedback/${studentId}`)
  return data  // { suggestion_sensitivity, predicted_disengagement_windows, pacing_hints, previous_sessions }
}
