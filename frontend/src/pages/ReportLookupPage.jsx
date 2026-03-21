import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function ReportLookupPage() {
    const navigate = useNavigate()
    const [sessionId, setSessionId] = useState('')
    const [error, setError] = useState('')

    function handleSubmit(e) {
        e.preventDefault()
        const id = sessionId.trim()
        if (!id) {
            setError('Please enter a session ID.')
            return
        }
        navigate(`/report/${id}`)
    }

    return (
        <div className="min-h-screen flex items-center justify-center px-4"
            style={{ background: '#F7F7F5' }}>

            <motion.div
                initial={{ opacity: 0, y: 30, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="relative z-10 w-full max-w-md bg-white rounded-2xl p-8"
                style={{ border: '1px solid #E8E8E8', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}
            >
                {/* Logo */}
                <div className="flex items-center gap-3 mb-8">
                    <div className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center">
                        <span className="text-white font-extrabold">E</span>
                    </div>
                    <span className="font-bold text-xl text-primary">Empath</span>
                </div>

                <h1 className="text-3xl font-extrabold text-primary mb-2">View Past Report</h1>
                <p className="text-secondary text-sm mb-8 leading-relaxed">
                    Enter a session ID to view the analytics dashboard.
                    Session IDs are shown in the report URL after each session.
                </p>

                <div className="h-px bg-border-light mb-8" />

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-xs text-secondary uppercase tracking-widest mb-2">Session ID</label>
                        <input
                            value={sessionId}
                            onChange={e => setSessionId(e.target.value)}
                            placeholder="e.g. 982adae0-9f55-4f2f-8565-..."
                            autoFocus
                        />
                    </div>

                    {error && (
                        <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-3 border border-red-100">{error}</p>
                    )}

                    <button
                        type="submit"
                        className="w-full btn-black text-base py-4 mt-2"
                    >
                        View Report →
                    </button>
                </form>

                <p className="text-secondary text-xs text-center mt-6">
                    Or <button onClick={() => navigate('/start')} className="text-primary underline">start a new session</button>
                </p>
            </motion.div>

            <div className="absolute bottom-8 text-center w-full">
                <button onClick={() => navigate('/')} className="text-secondary text-sm hover:text-primary transition-colors">
                    ← Back to home
                </button>
            </div>
        </div>
    )
}
