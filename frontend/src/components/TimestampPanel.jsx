import { motion } from 'framer-motion'

const EMOTION_COLORS = {
    focused: '#4ADE80', confused: '#FB923C',
    bored: '#F472B6', distressed: '#F87171', distracted: '#A78BFA',
}
const EMOTION_EMOJI = {
    focused: '😊', confused: '🤔', bored: '😴', distressed: '😟', distracted: '🫠'
}

function formatTime(s) {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function TimestampPanel({ elapsedSeconds, videoTime, emotion, seqiScore, seqiComponents, trendSlope, suggestion, eventLog }) {
    const color = EMOTION_COLORS[emotion] || '#888'

    return (
        <div className="w-72 shrink-0 flex flex-col gap-3 overflow-y-auto max-h-[calc(100vh-100px)]"
            style={{ scrollbarWidth: 'thin' }}>

            {/* Current State */}
            <div className="rounded-2xl p-4" style={{ background: '#1A1A1A', border: '1px solid #2A2A2A' }}>
                <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">Live Status</div>

                <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400 text-xs">Video Time</span>
                    <span className="text-white font-mono text-sm">{formatTime(Math.floor(videoTime || 0))}</span>
                </div>

                <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400 text-xs">Session</span>
                    <span className="text-gray-300 font-mono text-sm">{formatTime(elapsedSeconds)}</span>
                </div>

                <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400 text-xs">Emotion</span>
                    <span className="px-3 py-1 rounded-full text-xs font-bold text-black"
                        style={{ backgroundColor: color }}>
                        {EMOTION_EMOJI[emotion]} {emotion}
                    </span>
                </div>

                <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400 text-xs">SEQI Score</span>
                    <span className="text-white font-bold text-lg">{seqiScore}</span>
                </div>

                <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-xs">Trend</span>
                    <span className={`text-sm font-bold ${trendSlope > 1 ? 'text-green-400' : trendSlope < -1 ? 'text-red-400' : 'text-gray-400'}`}>
                        {trendSlope > 1 ? '↑ Improving' : trendSlope < -1 ? '↓ Declining' : '→ Stable'}
                    </span>
                </div>
            </div>

            {/* SEQI Components */}
            {seqiComponents && (
                <div className="rounded-2xl p-4" style={{ background: '#1A1A1A', border: '1px solid #2A2A2A' }}>
                    <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">SEQI Breakdown</div>
                    {[
                        { label: 'Behavioral', value: seqiComponents.be, color: '#4ADE80' },
                        { label: 'Stability', value: seqiComponents.es, color: '#60A5FA' },
                        { label: 'Interaction', value: seqiComponents.id, color: '#FACC15' },
                        { label: 'Recovery', value: seqiComponents.rr, color: '#FB923C' },
                    ].map(comp => (
                        <div key={comp.label} className="mb-2">
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-400">{comp.label}</span>
                                <span className="text-white">{Math.round(comp.value)}</span>
                            </div>
                            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full rounded-full"
                                    style={{ backgroundColor: comp.color }}
                                    animate={{ width: `${comp.value}%` }}
                                    transition={{ duration: 0.5 }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Active Suggestion */}
            {suggestion && (
                <div className="rounded-2xl p-4" style={{
                    background: '#1A1A1A', border: '1px solid #2A2A2A',
                    borderLeft: `3px solid ${color}`
                }}>
                    <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">Suggestion</div>
                    <p className="text-sm text-white leading-relaxed">{suggestion.suggestion}</p>
                    <span className="inline-block mt-2 px-2 py-1 rounded-full text-xs"
                        style={{ background: `${color}20`, color }}>
                        {suggestion.action?.replace(/_/g, ' ')}
                    </span>
                </div>
            )}

            {/* Event Log */}
            <div className="rounded-2xl p-4" style={{ background: '#1A1A1A', border: '1px solid #2A2A2A' }}>
                <div className="text-xs text-gray-500 uppercase tracking-widest mb-3">Event Log</div>
                <div className="space-y-1.5 max-h-40 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                    {(!eventLog || eventLog.length === 0) ? (
                        <div className="text-gray-600 text-xs">No events yet...</div>
                    ) : eventLog.slice(-15).reverse().map((ev, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="text-gray-600 font-mono shrink-0">{formatTime(ev.timestamp)}</span>
                            <span className="text-gray-400">{ev.type.replace(/_/g, ' ')}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
