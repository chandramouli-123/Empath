import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { generateQuiz, submitQuiz } from '../api'
import { useSession } from '../context/SessionContext'

const STATES = {
    PROMPT: 'prompt',
    LOADING: 'loading',
    QUIZ: 'quiz',
    SUBMITTING: 'submitting',
    RESULTS: 'results',
    ERROR: 'error',
}

export default function QuizPage() {
    const { sessionId } = useParams()
    const navigate = useNavigate()
    const { studentId } = useSession()
    const [state, setState] = useState(STATES.PROMPT)
    const [questions, setQuestions] = useState([])
    const [currentQ, setCurrentQ] = useState(0)
    const [answers, setAnswers] = useState([])  // stores selected option letter: "A", "B", etc.
    const [results, setResults] = useState(null)
    const [error, setError] = useState('')

    async function handleStart() {
        setState(STATES.LOADING)
        try {
            const data = await generateQuiz(sessionId)
            if (!data.questions || data.questions.length === 0) {
                setError('Could not generate questions for this video.')
                setState(STATES.ERROR)
                return
            }
            setQuestions(data.questions)
            setAnswers(new Array(data.questions.length).fill(''))
            setState(STATES.QUIZ)
        } catch (e) {
            setError('Failed to generate quiz. Please try again.')
            setState(STATES.ERROR)
        }
    }

    function handleOptionSelect(letter) {
        const newAnswers = [...answers]
        newAnswers[currentQ] = letter
        setAnswers(newAnswers)
    }

    async function handleSubmit() {
        setState(STATES.SUBMITTING)
        try {
            const data = await submitQuiz(sessionId, studentId || 'student_001', answers)
            setResults(data)
            setState(STATES.RESULTS)
        } catch (e) {
            setError('Failed to submit quiz.')
            setState(STATES.ERROR)
        }
    }

    function getScoreColor(score) {
        if (score >= 70) return '#4ADE80'
        if (score >= 50) return '#FACC15'
        if (score >= 30) return '#FB923C'
        return '#F87171'
    }

    const q = questions[currentQ]
    const options = q?.options || {}

    return (
        <div className="min-h-screen bg-white text-primary">

            {/* Header */}
            <div className="flex items-center justify-between px-8 py-5 border-b border-border-light bg-white sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/')} className="text-secondary hover:text-primary text-sm transition-colors">
                        ← Home
                    </button>
                    <span className="text-border-light">|</span>
                    <button onClick={() => navigate(`/report/${sessionId}`)}
                        className="text-secondary hover:text-primary text-sm transition-colors">
                        Report
                    </button>
                </div>
                <h1 className="text-lg font-bold text-primary">Knowledge Quiz</h1>
                <div style={{ width: 100 }} />
            </div>

            <div className="max-w-2xl mx-auto px-8 py-12">

                {/* PROMPT */}
                {state === STATES.PROMPT && (
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                        className="text-center">
                        <div className="text-6xl mb-6">📝</div>
                        <h2 className="text-2xl font-bold text-primary mb-3">Ready for a quiz?</h2>
                        <p className="text-secondary text-sm mb-4 max-w-md mx-auto">
                            4 multiple-choice questions (3 conceptual + 1 applied scenario) tailored to your learning session.
                        </p>
                        <p className="text-xs text-gray-400 mb-8">
                            AI-powered assessment with instant grading and explanations
                        </p>
                        <div className="flex justify-center gap-4">
                            <button onClick={handleStart} className="btn-black px-8 py-3">Generate Quiz →</button>
                            <button onClick={() => navigate(`/report/${sessionId}`)} className="btn-ghost px-8 py-3">Skip</button>
                        </div>
                    </motion.div>
                )}

                {/* LOADING */}
                {state === STATES.LOADING && (
                    <div className="text-center py-16">
                        <div className="animate-spin w-10 h-10 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4" />
                        <p className="text-secondary text-sm">Generating MCQ questions from video transcript...</p>
                        <p className="text-xs text-gray-400 mt-2">This may take 10-20 seconds</p>
                    </div>
                )}

                {/* QUIZ — MCQ format */}
                {state === STATES.QUIZ && q && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                        {/* Progress */}
                        <div className="flex items-center gap-3 mb-8">
                            {questions.map((_, i) => (
                                <div key={i} className="flex-1 h-1.5 rounded-full overflow-hidden bg-border-light">
                                    <div className={`h-full rounded-full transition-all duration-300 ${i < currentQ ? 'bg-green-400' : i === currentQ ? 'bg-primary' : 'bg-transparent'
                                        }`} style={{ width: i <= currentQ ? '100%' : '0%' }} />
                                </div>
                            ))}
                        </div>

                        <div className="text-xs text-secondary uppercase tracking-widest">
                            Question {currentQ + 1} of {questions.length}
                            <span className="ml-2 px-2 py-0.5 rounded-full bg-surface text-xs">
                                {q.type}
                            </span>
                        </div>

                        <h3 className="text-xl font-bold text-primary leading-relaxed">
                            {q.question}
                        </h3>

                        {/* MCQ Options */}
                        <div className="space-y-3 mt-6">
                            {Object.entries(options).map(([letter, text]) => {
                                const isSelected = answers[currentQ] === letter
                                return (
                                    <button
                                        key={letter}
                                        onClick={() => handleOptionSelect(letter)}
                                        className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all duration-200 ${isSelected
                                                ? 'border-primary bg-primary/5 ring-2 ring-primary/20'
                                                : 'border-border-light hover:border-gray-300 hover:bg-surface'
                                            }`}
                                    >
                                        <div className="flex items-start gap-3">
                                            <span className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${isSelected ? 'bg-primary text-white' : 'bg-surface text-secondary'
                                                }`}>
                                                {letter}
                                            </span>
                                            <span className={`text-sm leading-relaxed pt-1 ${isSelected ? 'text-primary font-medium' : 'text-secondary'}`}>
                                                {text}
                                            </span>
                                        </div>
                                    </button>
                                )
                            })}
                        </div>

                        <div className="flex justify-between mt-8">
                            <button
                                onClick={() => setCurrentQ(q => q - 1)}
                                disabled={currentQ === 0}
                                className="btn-ghost px-6 py-2 disabled:opacity-30"
                            >
                                ← Previous
                            </button>

                            {currentQ < questions.length - 1 ? (
                                <button onClick={() => setCurrentQ(q => q + 1)} className="btn-black px-6 py-2"
                                    disabled={!answers[currentQ]}>
                                    Next →
                                </button>
                            ) : (
                                <button onClick={handleSubmit} className="btn-black px-6 py-2"
                                    disabled={answers.some(a => !a)}>
                                    Submit Quiz →
                                </button>
                            )}
                        </div>
                    </motion.div>
                )}

                {/* SUBMITTING */}
                {state === STATES.SUBMITTING && (
                    <div className="text-center py-16">
                        <div className="animate-spin w-10 h-10 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4" />
                        <p className="text-secondary text-sm">Grading your answers...</p>
                    </div>
                )}

                {/* RESULTS */}
                {state === STATES.RESULTS && results && (
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                        className="space-y-8">
                        <div className="text-center">
                            <div className="text-6xl mb-4">
                                {results.total_score >= 75 ? '🎉' : results.total_score >= 50 ? '👍' : '📚'}
                            </div>
                            <div className="text-5xl font-extrabold" style={{ color: getScoreColor(results.total_score) }}>
                                {Math.round(results.total_score)}%
                            </div>
                            <p className="text-secondary text-sm mt-2">
                                {results.scores.filter(s => s.score === 100).length} / {results.scores.length} correct
                            </p>
                        </div>

                        <div className="space-y-4">
                            {results.scores.map((score, i) => {
                                const isCorrect = score.score === 100
                                const q = questions[i]
                                return (
                                    <div key={i} className={`rounded-xl p-5 border-2 ${isCorrect
                                            ? 'border-green-200 bg-green-50'
                                            : 'border-red-200 bg-red-50'
                                        }`}>
                                        <div className="flex items-start justify-between mb-3">
                                            <span className="text-xs text-secondary font-medium uppercase tracking-wider">
                                                Q{i + 1} — {q?.type || 'question'}
                                            </span>
                                            <span className={`px-3 py-1 rounded-full text-xs font-bold ${isCorrect ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                                                }`}>
                                                {isCorrect ? '✓ Correct' : '✗ Wrong'}
                                            </span>
                                        </div>
                                        <p className="text-sm text-primary font-medium mb-3">{q?.question}</p>

                                        {/* Show selected vs correct */}
                                        {!isCorrect && (
                                            <div className="space-y-1 mb-3">
                                                <div className="flex items-center gap-2 text-sm">
                                                    <span className="w-6 h-6 rounded-full bg-red-200 text-red-700 flex items-center justify-center text-xs font-bold">
                                                        {score.selected}
                                                    </span>
                                                    <span className="text-red-600 line-through">
                                                        {q?.options?.[score.selected] || answers[i]}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2 text-sm">
                                                    <span className="w-6 h-6 rounded-full bg-green-200 text-green-700 flex items-center justify-center text-xs font-bold">
                                                        {score.correct}
                                                    </span>
                                                    <span className="text-green-700 font-medium">
                                                        {q?.options?.[score.correct]}
                                                    </span>
                                                </div>
                                            </div>
                                        )}

                                        {score.feedback && (
                                            <p className="text-xs text-secondary italic border-t border-gray-200 pt-2 mt-2">
                                                {score.feedback}
                                            </p>
                                        )}
                                    </div>
                                )
                            })}
                        </div>

                        <div className="flex justify-center gap-4 pt-4">
                            <button onClick={() => navigate(`/report/${sessionId}`)} className="btn-black px-8 py-3">
                                View Full Report →
                            </button>
                            <button onClick={() => navigate('/')} className="btn-ghost px-8 py-3">Home</button>
                        </div>
                    </motion.div>
                )}

                {/* ERROR */}
                {state === STATES.ERROR && (
                    <div className="text-center py-12">
                        <div className="text-5xl mb-4">😵</div>
                        <p className="text-red-500 mb-2">{error}</p>
                        <p className="text-xs text-gray-400 mb-4">
                            Make sure Ollama is running: <code className="bg-surface px-2 py-1 rounded">ollama serve</code>
                        </p>
                        <div className="flex justify-center gap-4">
                            <button onClick={handleStart} className="btn-black px-6 py-2">Retry</button>
                            <button onClick={() => navigate(`/report/${sessionId}`)} className="btn-ghost px-6 py-2">Back to Report</button>
                        </div>
                    </div>
                )}

            </div>
        </div>
    )
}
