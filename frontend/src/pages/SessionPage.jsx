import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useSession } from '../context/SessionContext'
import { useWebcam } from '../hooks/useWebcam'
import VideoPlayer from '../components/VideoPlayer'
import TimestampPanel from '../components/TimestampPanel'
import VideoInfoPanel from '../components/VideoInfoPanel'
import { analyzeEmotion, computeScore, getSuggestion, sendBehaviorEvent, sendTabSwitch, endSession, getVideoInfo } from '../api'

// 6 emotion classes: focused, neutral, confused, bored, distressed, distracted
const EMOTION_COLORS = {
  focused: '#4ADE80', neutral: '#60A5FA', confused: '#FB923C',
  bored: '#F472B6', distressed: '#F87171', distracted: '#A78BFA',
}
const EMOTION_EMOJI = {
  focused: '😊', neutral: '😐', confused: '🤔', bored: '😴', distressed: '😟', distracted: '🫠'
}

function SEQIChartSection({ chartData, emotion }) {
  const color = EMOTION_COLORS[emotion] || '#888'
  return (
    <div className="w-full mt-4 rounded-2xl p-5" style={{ background: '#1A1A1A', border: '1px solid #2A2A2A' }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-gray-400 uppercase tracking-widest">SEQI Timeline</span>
        <span className="text-xs text-gray-600">Last 2 minutes</span>
      </div>
      {chartData.length < 2 ? (
        <div className="h-24 flex items-center justify-center text-gray-600 text-sm">Collecting data...</div>
      ) : (
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" hide />
            <YAxis domain={[0, 100]} hide />
            <Tooltip
              contentStyle={{ background: '#1E1E1E', border: '1px solid #2A2A2A', borderRadius: 8, fontSize: 12 }}
              formatter={(v) => [`${v}`, 'SEQI']}
            />
            <ReferenceLine y={70} stroke="#2A2A2A" strokeDasharray="3 3" />
            <ReferenceLine y={40} stroke="#2A2A2A" strokeDasharray="3 3" />
            <Line
              type="monotone" dataKey="score" stroke={color} strokeWidth={2}
              dot={false} activeDot={{ r: 4, fill: color }} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export default function SessionPage() {
  const navigate = useNavigate()
  const { sessionId, studentId, topic, videoUrl, clearSession, feedbackAdjustments } = useSession()
  const { videoRef, canvasRef, hasPermission, requestPermission, captureFrame, stopStream } = useWebcam()

  const [emotion, setEmotion] = useState('focused')
  const [manualEmotion, setManualEmotion] = useState(null)
  const manualEmotionRef = useRef(null)
  const phoneDetectedUntilRef = useRef(null)

  function handleSetManualEmotion(emo) {
    setManualEmotion(emo)
    manualEmotionRef.current = emo
    if (emo) {
      setEmotion(emo)
      if (sessionId) {
        const isCurrentlyDistracted = phoneDetected || Boolean(phoneDetectedUntilRef.current && Date.now() < phoneDetectedUntilRef.current)
        computeScore(
          sessionId, emo, 0.95, recentEventsRef.current, elapsedRef.current,
          isCurrentlyDistracted, isCurrentlyDistracted ? ['phone_detected'] : []
        )
          .then(res => {
            setSeqiScore(res.seqi_score || res.focus_score)
            setSeqiComponents({ be: res.be, es: res.es, id: res.id, rr: res.rr })
            setTrendSlope(res.trend_slope || 0)
            setIsDistracted(res.is_distracted || isCurrentlyDistracted)
          })
          .catch(() => {})
      }
    }
  }

  const [seqiScore, setSeqiScore] = useState(70)
  const [seqiComponents, setSeqiComponents] = useState({ be: 70, es: 80, id: 50, rr: 80 })
  const [trendSlope, setTrendSlope] = useState(0)
  const [isDistracted, setIsDistracted] = useState(false)
  const [phoneDetected, setPhoneDetected] = useState(false)
  const [pauseForMissingFace, setPauseForMissingFace] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [chartData, setChartData] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [eventLog, setEventLog] = useState([])
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [videoTime, setVideoTime] = useState(0)
  const [isEnding, setIsEnding] = useState(false)
  const isEndingRef = useRef(false)
  const [videoInfo, setVideoInfo] = useState(null)

  const recentEventsRef = useRef([])
  const lastSuggestionStateRef = useRef(null)
  const analyzeIntervalRef = useRef(null)
  const timerRef = useRef(null)
  const elapsedRef = useRef(0)
  const idleTimerRef = useRef(null)
  const idleFiredRef = useRef(false)
  const behavioralSummaryRef = useRef({})
  const videoTimeRef = useRef(0)
  const isAnalyzingRef = useRef(false)
  const missingFaceCountRef = useRef(0)
  const autoPausedForFaceRef = useRef(false)
  const resumeTokenRef = useRef(0)

  // Determine suggestion sensitivity from feedback
  const sensitivityRef = useRef(feedbackAdjustments?.suggestion_sensitivity || 1.0)

  // Track YouTube playback time
  function handleTimeUpdate(t) {
    videoTimeRef.current = t
    setVideoTime(t)
  }

  // Redirect if no session (but NOT during end-session flow)
  useEffect(() => {
    if (!sessionId && !isEndingRef.current) navigate('/start')
  }, [sessionId])

  // Request webcam + start elapsed timer + fetch video info on mount
  useEffect(() => {
    requestPermission()
    timerRef.current = setInterval(() => {
      setElapsedSeconds(s => {
        elapsedRef.current = s + 1
        return s + 1
      })
    }, 1000)

    // Fetch YT video info (title, description, chapters)
    if (videoUrl) {
      getVideoInfo(videoUrl)
        .then(info => { if (info && info.title) setVideoInfo(info) })
        .catch(() => { })
    }

    return () => {
      clearInterval(timerRef.current)
      stopAnalyzeLoop()
    }
  }, [])

  // Tab visibility detection
  useEffect(() => {
    function handleVisibility() {
      if (!sessionId) return
      const isVisible = !document.hidden
      const ts = elapsedRef.current
      sendTabSwitch(sessionId, ts, isVisible)
      if (!isVisible) {
        addEventLog(ts, 'tab_switch')
        recentEventsRef.current = [...recentEventsRef.current.slice(-9), 'tab_switch']
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [sessionId])

  // Idle detection — send idle_start after 30s of no interaction
  useEffect(() => {
    function resetIdle() {
      idleFiredRef.current = false
      clearTimeout(idleTimerRef.current)
      idleTimerRef.current = setTimeout(() => {
        if (!idleFiredRef.current && sessionId) {
          idleFiredRef.current = true
          const ts = elapsedRef.current
          recentEventsRef.current = [...recentEventsRef.current.slice(-9), 'idle_start']
          sendBehaviorEvent(sessionId, ts, 'idle_start')
          addEventLog(ts, 'idle_start')
        }
      }, 30000)
    }
    window.addEventListener('mousemove', resetIdle)
    window.addEventListener('keydown', resetIdle)
    window.addEventListener('click', resetIdle)
    resetIdle()
    return () => {
      clearTimeout(idleTimerRef.current)
      window.removeEventListener('mousemove', resetIdle)
      window.removeEventListener('keydown', resetIdle)
      window.removeEventListener('click', resetIdle)
    }
  }, [sessionId])

  // Start analyze loop when webcam is ready
  useEffect(() => {
    if (hasPermission === true) startAnalyzeLoop()
    return () => stopAnalyzeLoop()
  }, [hasPermission])

  function addEventLog(timestamp, type) {
    setEventLog(prev => [...prev.slice(-50), { timestamp, type }])
  }

  function startAnalyzeLoop() {
    analyzeIntervalRef.current = setInterval(analyzeFrame, 2000)
  }

  function stopAnalyzeLoop() {
    if (analyzeIntervalRef.current) clearInterval(analyzeIntervalRef.current)
  }

  async function analyzeFrame() {
    if (!sessionId || isEndingRef.current || isAnalyzingRef.current) return
    isAnalyzingRef.current = true

    try {
      const blob = await captureFrame()
      if (!blob) return

      const ts = elapsedRef.current

      // Always analyze webcam frame in background for phone & object detection
      const emotionResult = await analyzeEmotion(blob).catch(err => {
        console.error('analyzeEmotion error:', err)
        return null
      })

      const detectedPhone = Boolean(emotionResult?.phone_detected)
      const faceDetected = emotionResult?.face_detected !== false

      // Apply phone results before the face-presence gate. A phone can remain
      // visible even when the face detector temporarily misses the face.
      if (detectedPhone) {
        setPhoneDetected(true)
        phoneDetectedUntilRef.current = Date.now() + 4000
        recentEventsRef.current = [...recentEventsRef.current.slice(-9), 'phone_detected']
        sendBehaviorEvent(sessionId, ts, 'phone_detected').catch(() => {})
        addEventLog(ts, 'phone_detected')
      } else if (phoneDetectedUntilRef.current && Date.now() >= phoneDetectedUntilRef.current) {
        setPhoneDetected(false)
        phoneDetectedUntilRef.current = null
      }

      if (!faceDetected) {
        missingFaceCountRef.current += 1
        if (missingFaceCountRef.current >= 2 && !autoPausedForFaceRef.current) {
          autoPausedForFaceRef.current = true
          setPauseForMissingFace(true)
          setEmotion('distracted')
          setIsDistracted(true)
          const scoreResult = await computeScore(
            sessionId,
            'distracted',
            1,
            recentEventsRef.current,
            ts,
            true,
            ['face_missing']
          )
          const score = scoreResult.seqi_score ?? scoreResult.focus_score ?? 0
          setSeqiScore(score)
          setSeqiComponents({ be: scoreResult.be, es: scoreResult.es, id: scoreResult.id, rr: scoreResult.rr })
          setTrendSlope(scoreResult.trend_slope || 0)
          setChartData(prev => [...prev.slice(-60), { time: ts, score, emotion: 'distracted' }])
          addEventLog(ts, 'face_missing_pause')
        }
        return
      }

      const faceReturned = missingFaceCountRef.current > 0
      missingFaceCountRef.current = 0
      if (faceReturned && autoPausedForFaceRef.current) {
        autoPausedForFaceRef.current = false
        setPauseForMissingFace(false)
        resumeTokenRef.current += 1
        setIsDistracted(false)
      }

      const modelEmotion = emotionResult?.emotion || 'focused'
      const modelConf = emotionResult?.confidence || 0.95

      // Respect manual demo override if selected; otherwise use model detected emotion
      const isManual = Boolean(manualEmotionRef.current)
      const effectiveEmotion = manualEmotionRef.current || modelEmotion
      const effectiveConf = isManual ? 0.95 : modelConf

      const isCurrentlyDistracted = effectiveEmotion === 'distracted'
        || detectedPhone
        || Boolean(phoneDetectedUntilRef.current && Date.now() < phoneDetectedUntilRef.current)

      const events = recentEventsRef.current
      const scoreResult = await computeScore(
        sessionId, effectiveEmotion, effectiveConf, events, ts,
        isCurrentlyDistracted, isCurrentlyDistracted ? ['phone_detected'] : []
      )

      const score = scoreResult.seqi_score ?? scoreResult.focus_score ?? 70
      const state = scoreResult.engagement_state || 'focused'

      // Clear consumed events
      recentEventsRef.current = []

      setEmotion(effectiveEmotion)
      setSeqiScore(score)
      setSeqiComponents({ be: scoreResult.be, es: scoreResult.es, id: scoreResult.id, rr: scoreResult.rr })
      setTrendSlope(scoreResult.trend_slope || 0)
      setIsDistracted(scoreResult.is_distracted || isCurrentlyDistracted)
      setChartData(prev => [...prev.slice(-60), { time: ts, score, emotion: effectiveEmotion }])

      // Update behavioral summary for suggestions
      behavioralSummaryRef.current = {
        rewinds: events.filter(e => e === 'rewind').length,
        pauses: events.filter(e => e === 'pause').length,
        fast_forwards: events.filter(e => e === 'fast_forward').length,
        idles: events.filter(e => e === 'idle_start').length,
        tab_switches: events.filter(e => e === 'tab_switch').length,
      }

      addEventLog(ts, `score:${score}`)

      // Suggestion logic — adjusted by sensitivity
      const threshold = Math.round(50 * sensitivityRef.current)
      if (score < threshold && state !== lastSuggestionStateRef.current) {
        lastSuggestionStateRef.current = state
        const sugResult = await getSuggestion(
          sessionId, state, topic, ts,
          behavioralSummaryRef.current,
          scoreResult.trend_slope || 0
        )
        if (sugResult.suggestion) {
          const newSuggestion = { ...sugResult, timestamp: ts, id: Date.now() }
          setSuggestion(newSuggestion)
          setSuggestions(prev => [newSuggestion, ...prev].slice(0, 10))
          addEventLog(ts, 'suggestion')
          setTimeout(() => setSuggestion(null), 8000)
        }
      }
    } catch (err) {
      console.error('analyze error:', err)
    } finally {
      isAnalyzingRef.current = false
    }
  }

  async function handleBehaviorEvent(type, ts) {
    if (!sessionId) return
    recentEventsRef.current = [...recentEventsRef.current.slice(-9), type]
    await sendBehaviorEvent(sessionId, ts, type)
    addEventLog(ts, type)
  }

  async function handleEndSession() {
    if (isEnding) return
    setIsEnding(true)
    isEndingRef.current = true  // prevent useEffect from redirecting to /start
    stopAnalyzeLoop()
    clearInterval(timerRef.current)
    stopStream()
    const id = sessionId
    try { await endSession(id) } catch { }
    clearSession()
    navigate(`/report/${id}`)
  }

  function formatTime(s) {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const emotionColor = EMOTION_COLORS[emotion] || '#888'

  if (!sessionId) return null

  return (
    <div className="min-h-screen text-white flex flex-col" style={{ background: '#0F0F0F' }}>

      {/* Top bar */}
      <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3"
        style={{
          background: 'rgba(15,15,15,0.85)', backdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(255,255,255,0.06)'
        }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <span className="text-black font-extrabold text-xs">E</span>
          </div>
          <span className="text-gray-300 text-sm truncate max-w-xs">{topic}</span>
          {phoneDetected && (
            <span className="px-3 py-1 rounded-full text-xs font-bold text-white bg-red-600 shadow-[0_0_15px_rgba(239,68,68,0.7)] animate-pulse flex items-center gap-1.5">
              <span>📱</span> PHONE DETECTED
            </span>
          )}
          {isDistracted && !phoneDetected && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold text-white bg-purple-500/80 animate-pulse">
              DISTRACTED
            </span>
          )}
        </div>
        <div className="text-white font-mono text-lg tabular-nums">{formatTime(elapsedSeconds)}</div>
        <button
          onClick={handleEndSession}
          disabled={isEnding}
          className="px-5 py-2 rounded-full border border-red-500/40 text-red-400 text-sm
                     hover:bg-red-500 hover:text-white hover:border-red-500 transition-all disabled:opacity-50"
        >
          {isEnding ? 'Ending...' : 'End Session'}
        </button>
      </div>

      {/* Main content with side panel */}
      <div className="flex-1 flex gap-4 px-4 pt-16 pb-4">

        {/* Left — Video + Chart */}
        <div className="flex-1 flex flex-col items-center min-w-0">
          {/* Video area */}
          <div className={`relative w-full max-w-5xl rounded-2xl transition-all duration-500 ${
            phoneDetected ? 'ring-2 ring-red-500 shadow-[0_0_35px_rgba(239,68,68,0.35)]' : ''
          }`}>
            <VideoPlayer
              url={videoUrl}
              pauseForMissingFace={pauseForMissingFace}
              resumeToken={resumeTokenRef.current}
              onPause={(ts) => handleBehaviorEvent('pause', ts)}
              onPlay={(ts) => handleBehaviorEvent('play', ts)}
              onSeek={(type, ts) => handleBehaviorEvent(type, ts)}
              onTimeUpdate={handleTimeUpdate}
            />

            {/* SEQI Score Ring — top-right */}
            <motion.div
              className="absolute top-4 right-4 z-10"
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ duration: 0.4 }}
              key={seqiScore}
            >
              <div className="flex flex-col items-center justify-center p-3 rounded-2xl"
                style={{
                  background: 'rgba(15,15,15,0.75)', backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(255,255,255,0.08)', width: 100, height: 100
                }}>
                <svg className="absolute" width="90" height="90" viewBox="0 0 90 90">
                  <circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
                  <circle
                    cx="45" cy="45" r="38" fill="none" stroke={emotionColor}
                    strokeWidth="6" strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 38}`}
                    strokeDashoffset={`${2 * Math.PI * 38 * (1 - seqiScore / 100)}`}
                    transform="rotate(-90 45 45)"
                    style={{ transition: 'stroke-dashoffset 0.5s ease, stroke 0.5s ease' }}
                  />
                </svg>
                <span className="relative text-2xl font-extrabold text-white">{seqiScore}</span>
                <span className="relative text-xs text-gray-400">SEQI</span>
              </div>
            </motion.div>

            {/* Emotion pill — bottom left */}
            <AnimatePresence mode="wait">
              <motion.div
                key={emotion}
                className="absolute bottom-4 left-4 px-4 py-2 rounded-full text-sm font-bold text-black z-10"
                style={{ backgroundColor: emotionColor }}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              >
                {EMOTION_EMOJI[emotion]} {emotion}
              </motion.div>
            </AnimatePresence>

            {/* Phone detected warning */}
            <AnimatePresence>
              {phoneDetected && (
                <motion.div
                  className="absolute bottom-5 left-1/2 -translate-x-1/2 px-6 py-2.5 rounded-full text-sm font-bold text-white z-30 flex items-center gap-2.5 shadow-2xl backdrop-blur-md"
                  style={{
                    backgroundColor: 'rgba(220, 38, 38, 0.95)',
                    border: '1px solid rgba(254, 202, 202, 0.4)',
                    boxShadow: '0 8px 30px rgba(239, 68, 68, 0.6)'
                  }}
                  initial={{ opacity: 0, y: 25, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 25, scale: 0.9 }}
                  transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                >
                  <span className="text-xl animate-bounce">📱</span>
                  <span>Phone Detected</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* SEQI Chart */}
          <div className="w-full max-w-5xl">
            <SEQIChartSection chartData={chartData} emotion={emotion} />
          </div>

          {/* Video Info — title, description, chapters */}
          <VideoInfoPanel videoInfo={videoInfo} />

          {/* Past Suggestions */}
          {suggestions.length > 0 && (
            <div className="w-full max-w-5xl mt-3">
              <p className="text-xs text-gray-600 uppercase tracking-widest mb-2">Past Suggestions</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map(s => (
                  <span key={s.id} className="px-3 py-1 rounded-full text-xs border text-gray-400"
                    style={{ background: '#1A1A1A', borderColor: '#2A2A2A' }}>
                    [{Math.floor(s.timestamp / 60)}:{String(s.timestamp % 60).padStart(2, '0')}] {s.suggestion?.slice(0, 40)}...
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right — Timestamp Panel */}
        <TimestampPanel
          elapsedSeconds={elapsedSeconds}
          videoTime={videoTime}
          emotion={emotion}
          seqiScore={seqiScore}
          seqiComponents={seqiComponents}
          trendSlope={trendSlope}
          suggestion={suggestion}
          eventLog={eventLog}
          manualEmotion={manualEmotion}
          onSetManualEmotion={handleSetManualEmotion}
        />
      </div>

      {/* Webcam bubble — fixed bottom-right */}
      <div className="fixed bottom-6 right-6 z-50">
        <div className={`relative rounded-full overflow-hidden border-2 transition-all duration-300
                         ${phoneDetected
                            ? 'border-red-500 ring-4 ring-red-500/50 shadow-[0_0_25px_rgba(239,68,68,0.8)] animate-pulse'
                            : hasPermission ? 'border-green-400' : 'border-gray-600'}`}
          style={{
            width: 96, height: 96,
            boxShadow: phoneDetected
              ? '0 0 25px rgba(239,68,68,0.8), 0 4px 20px rgba(0,0,0,0.5)'
              : hasPermission
                ? '0 0 0 3px rgba(74,222,128,0.25), 0 4px 20px rgba(0,0,0,0.5)'
                : '0 4px 20px rgba(0,0,0,0.5)',
          }}>
          {hasPermission
            ? <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover scale-x-[-1]" />
            : <div className="w-full h-full flex items-center justify-center text-2xl"
              style={{ background: '#1A1A1A' }}>🔒</div>
          }
          {phoneDetected && (
            <div className="absolute inset-0 bg-red-950/40 flex items-center justify-center pointer-events-none">
              <span className="text-2xl drop-shadow-md animate-bounce">📱</span>
            </div>
          )}
        </div>
        <canvas ref={canvasRef} className="hidden" />
      </div>

      {/* Suggestion toast — fixed right */}
      <AnimatePresence>
        {suggestion && (
          <motion.div
            className="fixed right-80 top-20 w-80 z-50 rounded-2xl p-5"
            style={{
              background: 'rgba(15,15,15,0.85)', backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderLeft: `3px solid ${emotionColor}`,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 100 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          >
            <div className="flex justify-between items-start mb-3">
              <span className="text-xs text-gray-400 uppercase tracking-widest">Empath Suggests</span>
              <button onClick={() => setSuggestion(null)} className="text-gray-600 hover:text-white text-lg leading-none">×</button>
            </div>
            <p className="text-sm text-white leading-relaxed mb-3">{suggestion.suggestion}</p>
            <span className="inline-block px-3 py-1 rounded-full text-xs font-medium"
              style={{ background: `${emotionColor}20`, color: emotionColor }}>
              {suggestion.action?.replace(/_/g, ' ')}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
