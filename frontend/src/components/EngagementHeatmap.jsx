/**
 * EngagementHeatmap — Color-coded timeline showing SEQI mapped to video timestamps.
 * Green = Focused (70+), Yellow = Neutral (50-69), Orange = Struggling (30-49), Red = Critical (<30)
 */

const HEATMAP_COLORS = [
    { min: 70, color: '#4ADE80', label: 'Focused' },
    { min: 50, color: '#FACC15', label: 'Moderate' },
    { min: 30, color: '#FB923C', label: 'Struggling' },
    { min: 0, color: '#F87171', label: 'Critical' },
]

function getColor(score) {
    for (const { min, color } of HEATMAP_COLORS) {
        if (score >= min) return color
    }
    return '#F87171'
}

function formatTime(s) {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function EngagementHeatmap({ timeline, height = 40 }) {
    if (!timeline || timeline.length < 2) {
        return (
            <div className="w-full rounded-lg flex items-center justify-center text-gray-500 text-sm"
                style={{ height, background: '#1A1A1A' }}>
                Not enough data for heatmap
            </div>
        )
    }

    const maxT = timeline[timeline.length - 1].t || 1

    return (
        <div>
            <div className="w-full rounded-lg overflow-hidden flex" style={{ height }}>
                {timeline.map((point, i) => {
                    const nextT = timeline[i + 1]?.t || point.t + 2
                    const width = ((nextT - point.t) / maxT) * 100
                    const score = point.seqi ?? point.score ?? 50
                    return (
                        <div
                            key={i}
                            className="relative group"
                            style={{
                                width: `${Math.max(width, 0.5)}%`,
                                backgroundColor: getColor(score),
                                opacity: 0.85,
                                transition: 'opacity 0.2s',
                            }}
                            onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                            onMouseLeave={e => e.currentTarget.style.opacity = '0.85'}
                        >
                            {/* Tooltip */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50">
                                <div className="bg-black/90 text-white text-xs px-3 py-2 rounded-lg whitespace-nowrap shadow-lg">
                                    <div className="font-bold">{formatTime(point.t)}</div>
                                    <div>SEQI: {score}</div>
                                    <div className="capitalize">{point.emotion || '—'}</div>
                                </div>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Time labels */}
            <div className="flex justify-between mt-1.5">
                <span className="text-xs text-gray-500 font-mono">0:00</span>
                <span className="text-xs text-gray-500 font-mono">{formatTime(maxT)}</span>
            </div>

            {/* Legend */}
            <div className="flex gap-4 mt-2">
                {HEATMAP_COLORS.map(({ color, label }) => (
                    <div key={label} className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                        <span className="text-xs text-gray-400">{label}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}
