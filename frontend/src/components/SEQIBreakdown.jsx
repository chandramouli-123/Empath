/**
 * SEQIBreakdown — Radial breakdown showing all 4 SEQI components.
 */
import { motion } from 'framer-motion'

function RadialBar({ label, value, color, size = 60 }) {
    const r = (size - 8) / 2
    const circ = 2 * Math.PI * r
    return (
        <div className="flex flex-col items-center">
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E8E8E8" strokeWidth="4" />
                    <motion.circle
                        cx={size / 2} cy={size / 2} r={r}
                        fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
                        strokeDasharray={circ}
                        initial={{ strokeDashoffset: circ }}
                        animate={{ strokeDashoffset: circ * (1 - value / 100) }}
                        transition={{ duration: 1.2, ease: 'easeOut' }}
                        transform={`rotate(-90 ${size / 2} ${size / 2})`}
                    />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-sm font-bold text-primary">{Math.round(value)}</span>
                </div>
            </div>
            <span className="text-xs text-secondary mt-1.5">{label}</span>
        </div>
    )
}

export default function SEQIBreakdown({ seqi, be, es, id, rr }) {
    const components = [
        { label: 'Behavioral', value: be, color: '#4ADE80', weight: '40%' },
        { label: 'Stability', value: es, color: '#60A5FA', weight: '30%' },
        { label: 'Interaction', value: id, color: '#FACC15', weight: '20%' },
        { label: 'Recovery', value: rr, color: '#FB923C', weight: '10%' },
    ]

    return (
        <div>
            <div className="flex justify-center gap-6 flex-wrap">
                {components.map(comp => (
                    <div key={comp.label} className="text-center">
                        <RadialBar label={comp.label} value={comp.value} color={comp.color} />
                        <div className="text-xs text-gray-400 mt-0.5">×{comp.weight}</div>
                    </div>
                ))}
            </div>
            <div className="text-center mt-4">
                <div className="text-xs text-secondary uppercase tracking-widest">Combined SEQI</div>
                <div className="text-3xl font-extrabold text-primary mt-1">{Math.round(seqi)}</div>
            </div>
        </div>
    )
}
