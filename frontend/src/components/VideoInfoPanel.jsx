import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

function formatTime(seconds) {
    if (!seconds && seconds !== 0) return '0:00'
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    return `${m}:${s.toString().padStart(2, '0')}`
}

export default function VideoInfoPanel({ videoInfo, onSeekTo }) {
    const [showDesc, setShowDesc] = useState(false)

    if (!videoInfo || !videoInfo.title) return null

    const { title, description, chapters, duration, channel } = videoInfo

    return (
        <div className="w-full max-w-5xl mt-3">
            {/* Video title + channel */}
            <div className="rounded-2xl p-4" style={{ background: '#1A1A1A', border: '1px solid #2A2A2A' }}>

                <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                        <h3 className="text-white text-sm font-bold leading-snug truncate">{title}</h3>
                        <div className="flex items-center gap-3 mt-1">
                            {channel && <span className="text-gray-400 text-xs">{channel}</span>}
                            {duration > 0 && <span className="text-gray-500 text-xs">⏱ {formatTime(duration)}</span>}
                        </div>
                    </div>
                    {description && (
                        <button
                            onClick={() => setShowDesc(!showDesc)}
                            className="text-xs text-gray-500 hover:text-gray-300 transition-colors ml-3 shrink-0"
                        >
                            {showDesc ? 'Hide' : 'Description ▾'}
                        </button>
                    )}
                </div>

                {/* Description (collapsible) */}
                <AnimatePresence>
                    {showDesc && description && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                        >
                            <div className="mt-3 pt-3 border-t border-gray-800">
                                <p className="text-gray-400 text-xs leading-relaxed whitespace-pre-line max-h-40 overflow-y-auto"
                                    style={{ scrollbarWidth: 'thin' }}>
                                    {description}
                                </p>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Chapters / Timestamps */}
                {chapters && chapters.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-800">
                        <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">Chapters</div>
                        <div className="space-y-1 max-h-48 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                            {chapters.map((ch, i) => (
                                <button
                                    key={i}
                                    onClick={() => onSeekTo?.(ch.time)}
                                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left
                             hover:bg-white/5 transition-colors group"
                                >
                                    <span className="text-xs font-mono text-blue-400 shrink-0 w-12 group-hover:text-blue-300">
                                        {formatTime(ch.time)}
                                    </span>
                                    <span className="text-xs text-gray-300 truncate group-hover:text-white transition-colors">
                                        {ch.title}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
