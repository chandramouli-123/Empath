import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, PieChart, Pie, Cell } from 'recharts'
import { getSessionAnalytics } from '../api'
import BehaviorTimeline from '../components/BehaviorTimeline'
import EngagementHeatmap from '../components/EngagementHeatmap'
import SEQIBreakdown from '../components/SEQIBreakdown'

const EMOTION_COLORS = {
  focused: '#4ADE80', neutral: '#60A5FA', confused: '#FB923C',
  bored: '#F472B6', distressed: '#F87171', distracted: '#A78BFA',
}

const EMOTION_BG = {
  focused: '#DCFCE7', neutral: '#DBEAFE', confused: '#FFEDD5',
  bored: '#FCE7F3', distressed: '#FEF2F2', distracted: '#EDE9FE',
}

const RISK_STYLES = {
  green: { bg: '#DCFCE7', color: '#16A34A', label: 'Low Risk', icon: '✅' },
  yellow: { bg: '#FEF9C3', color: '#CA8A04', label: 'Moderate Risk', icon: '⚠️' },
  red: { bg: '#FEF2F2', color: '#DC2626', label: 'High Risk', icon: '🚨' },
}

function formatTime(s) {
  if (!s) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.round(s) % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds) % 60
  return m === 0 ? `${s}s` : `${m}m ${s}s`
}

function ScoreRing({ score }) {
  const color = score >= 70 ? '#4ADE80' : score >= 50 ? '#FACC15' : score >= 30 ? '#FB923C' : '#F87171'
  const r = 70
  const circ = 2 * Math.PI * r
  return (
    <div className="relative" style={{ width: 180, height: 180 }}>
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={r} fill="none" stroke="#E8E8E8" strokeWidth="10" />
        <circle cx="90" cy="90" r={r} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - score / 100)}
          transform="rotate(-90 90 90)" style={{ transition: 'stroke-dashoffset 1.2s ease' }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-extrabold text-primary">{Math.round(score)}</span>
        <span className="text-xs text-secondary mt-1">SEQI</span>
      </div>
    </div>
  )
}

export default function ReportPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getSessionAnalytics(sessionId)
      .then(setReport)
      .catch(() => setError('Could not load report. Session may have expired.'))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-secondary">Loading analytics...</div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-4">
        <p className="text-red-500">{error || 'Report not found.'}</p>
        <button onClick={() => navigate('/start')} className="btn-black">Start New Session</button>
      </div>
    )
  }

  const seqi = Math.round(report.final_seqi || 0)
  const risk = RISK_STYLES[report.risk_level] || RISK_STYLES.yellow
  const timeline = report.score_timeline || []
  const emotionDist = report.emotion_distribution || {}
  const emotions = Object.keys(emotionDist)
  const pieData = emotions.map(em => ({ name: em, value: emotionDist[em] || 0 }))
  const driftSegments = report.drift_segments || []
  const recoveryEvents = report.recovery_events || []
  const keySegments = report.key_segments || {}

  return (
    <div className="min-h-screen bg-white text-primary pb-16">

      {/* Header */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-border-light bg-white sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-secondary hover:text-primary text-sm transition-colors">
            ← Home
          </button>
          <span className="text-border-light">|</span>
          <button onClick={() => navigate('/start')} className="text-secondary hover:text-primary text-sm transition-colors">
            New Session
          </button>
        </div>
        <div className="text-center">
          <h1 className="text-lg font-bold text-primary">Session Analytics</h1>
          <p className="text-xs text-secondary">ID: {sessionId?.slice(0, 8)}...</p>
        </div>
        <button onClick={() => navigate(`/quiz/${sessionId}`)} className="btn-black px-4 py-2 text-xs">Take Quiz →</button>
      </div>

      {/* 1) Hero — Final SEQI + Risk */}
      <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center py-12 border-b border-border-light bg-surface">
        <p className="text-xs text-secondary uppercase tracking-widest mb-6">Final SEQI Score</p>
        <ScoreRing score={seqi} />
        <div className="flex items-center gap-2 mt-5">
          <span className="px-4 py-2 rounded-full text-sm font-bold" style={{ background: risk.bg, color: risk.color }}>
            {risk.icon} {risk.label}
          </span>
        </div>
        <p className="text-secondary text-xs mt-2">
          {formatDuration(report.total_time)} session · {report.behavior_events?.length || 0} events
        </p>
      </motion.div>

      <div className="max-w-5xl mx-auto px-8 space-y-10 mt-10">

        {/* SEQI Breakdown */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-6">SEQI Component Breakdown</h2>
          <div className="card-light">
            <SEQIBreakdown seqi={seqi} be={report.be} es={report.es} id={report.id} rr={report.rr} />
          </div>
        </section>

        {/* 2) Emotion Distribution Pie */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Emotion Distribution</h2>
          <div className="card-light flex flex-col md:flex-row items-center gap-8">
            <div style={{ width: 200, height: 200 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={80} innerRadius={40}>
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={EMOTION_COLORS[entry.name] || '#888'} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [`${v}%`]} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1">
              {emotions.map(em => (
                <div key={em} className="rounded-xl p-4 text-center border border-border-light"
                  style={{ borderTopColor: EMOTION_COLORS[em], borderTopWidth: 4, background: EMOTION_BG[em] || '#F7F7F5' }}>
                  <div className="text-xl font-extrabold text-primary">{Math.round(emotionDist[em])}%</div>
                  <div className="capitalize text-sm font-semibold text-primary mt-1">{em}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 3) Engagement Heatmap */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Engagement Heatmap</h2>
          <div className="card-light">
            <EngagementHeatmap timeline={timeline} height={48} />
          </div>
        </section>

        {/* Timeline chart */}
        {timeline.length > 1 && (
          <section>
            <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">SEQI Timeline</h2>
            <div className="card-light">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={timeline}>
                  <defs>
                    <linearGradient id="seqiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4ADE80" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#4ADE80" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="t" tickFormatter={v => formatTime(v)}
                    tick={{ fill: '#9CA3AF', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#9CA3AF', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #E8E8E8', borderRadius: 8, fontSize: 12 }}
                    formatter={(v) => [`${v}`, 'SEQI']} />
                  <ReferenceLine y={70} stroke="#E8E8E8" strokeDasharray="3 3"
                    label={{ value: 'Focused', fill: '#9CA3AF', fontSize: 10 }} />
                  <ReferenceLine y={40} stroke="#E8E8E8" strokeDasharray="3 3"
                    label={{ value: 'Struggling', fill: '#9CA3AF', fontSize: 10 }} />
                  <Area type="monotone" dataKey="seqi" stroke="#4ADE80" strokeWidth={2}
                    fill="url(#seqiGrad)" dot={false} activeDot={{ r: 4 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* 4) Cognitive Drift */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Cognitive Drift Detection</h2>
          {driftSegments.length > 0 ? (
            <div className="space-y-2">
              {driftSegments.map((seg, i) => (
                <div key={i} className="card-light flex items-center gap-4"
                  style={{ borderLeft: '3px solid #FB923C' }}>
                  <span className="text-xs font-mono text-secondary bg-surface px-2 py-1 rounded">
                    {formatTime(seg.start)} → {formatTime(seg.end)}
                  </span>
                  <span className="text-sm text-primary">
                    SEQI declined for {formatDuration(seg.duration)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="card-light text-center py-6">
              <p className="text-secondary text-sm">No cognitive drift detected — great consistency! ✨</p>
            </div>
          )}
        </section>

        {/* 5) Recovery Rate */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Recovery Rate Analysis</h2>
          {recoveryEvents.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {recoveryEvents.map((ev, i) => (
                <div key={i} className="card-light text-center">
                  <div className="text-xs text-secondary mb-1">Recovery #{i + 1}</div>
                  <div className="text-2xl font-bold text-primary">{formatDuration(ev.duration)}</div>
                  <div className="text-xs text-secondary mt-1">
                    {formatTime(ev.drop_at)} → {formatTime(ev.recovered_at)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card-light text-center py-6">
              <p className="text-secondary text-sm">No recovery events — you stayed focused throughout! 🎯</p>
            </div>
          )}
        </section>

        {/* 6) Learning Insights */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Learning Insights</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {keySegments.most_focused && (
              <div className="card-light text-center" style={{ borderTop: '3px solid #4ADE80' }}>
                <div className="text-xs text-secondary mb-2">🎯 Most Focused</div>
                <div className="text-lg font-bold text-primary">{formatTime(keySegments.most_focused.timestamp)}</div>
                <div className="text-xs text-secondary">SEQI: {keySegments.most_focused.score}</div>
              </div>
            )}
            {keySegments.most_distracted && (
              <div className="card-light text-center" style={{ borderTop: '3px solid #A78BFA' }}>
                <div className="text-xs text-secondary mb-2">🫠 Most Distracted</div>
                <div className="text-lg font-bold text-primary">{formatTime(keySegments.most_distracted.timestamp)}</div>
                <div className="text-xs text-secondary">SEQI: {keySegments.most_distracted.score}</div>
              </div>
            )}
            {keySegments.most_confusing && keySegments.most_confusing.duration > 0 && (
              <div className="card-light text-center" style={{ borderTop: '3px solid #FB923C' }}>
                <div className="text-xs text-secondary mb-2">🤔 Most Confusing</div>
                <div className="text-lg font-bold text-primary">
                  {formatTime(keySegments.most_confusing.start)} - {formatTime(keySegments.most_confusing.end)}
                </div>
                <div className="text-xs text-secondary">{formatDuration(keySegments.most_confusing.duration)}</div>
              </div>
            )}
          </div>
        </section>

        {/* 7) Personalized Suggestions */}
        <section>
          <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">
            Improvement Suggestions {report.suggestions_given?.length ? `(${report.suggestions_given.length})` : ''}
          </h2>
          {report.suggestions_given?.length > 0 ? (
            <div className="space-y-3">
              {report.suggestions_given.map((s, i) => (
                <div key={i} className="card-light flex items-start gap-4"
                  style={{ borderLeft: `3px solid ${EMOTION_COLORS[s.engagement_state] || '#888'}` }}>
                  <span className="text-xs text-secondary font-mono mt-0.5 shrink-0 bg-surface px-2 py-1 rounded-md">
                    {formatTime(s.timestamp_seconds)}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm text-primary">{s.suggestion_text}</p>
                    <span className="inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium bg-surface text-secondary">
                      {s.action?.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card-light text-center py-8">
              <p className="text-secondary text-sm">No suggestions needed — great session! 🎉</p>
            </div>
          )}
        </section>

        {/* Quiz Result (if taken) */}
        {report.quiz_result && (
          <section>
            <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Quiz Performance</h2>
            <div className="card-light text-center">
              <div className="text-4xl font-extrabold text-primary">{Math.round(report.quiz_result.total_score)}%</div>
              <div className="text-xs text-secondary mt-1">Quiz Score</div>
            </div>
          </section>
        )}

        {/* Behavior Events */}
        {report.behavior_events?.length > 0 && (
          <section>
            <h2 className="text-xs text-secondary uppercase tracking-widest mb-4">Behavior Events</h2>
            <BehaviorTimeline events={report.behavior_events} durationSeconds={report.total_time} />
          </section>
        )}

        {/* Actions */}
        <div className="flex justify-center gap-4 pt-4 pb-8">
          <button onClick={() => navigate(`/quiz/${sessionId}`)} className="btn-black px-8 py-3">Take Quiz →</button>
          <button onClick={() => navigate('/start')} className="btn-ghost px-8 py-3">New Session</button>
          <button onClick={() => navigator.clipboard.writeText(window.location.href)} className="btn-ghost px-8 py-3">
            Copy Link
          </button>
        </div>

      </div>
    </div>
  )
}
