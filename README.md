# Empath — Emotion-Aware Adaptive Learning Assistant

Empath reads your emotions in real time via webcam and adapts your video learning experience — so you stay focused and never fall behind.

## Features

- **Facial Emotion Detection** — Webcam frames analyzed every 2s using HuggingFace (`dima806/facial_emotions_image_detection`), all processed locally
- **Behavioral Engagement Tracking** — Pause, rewind, fast-forward, idle, and tab-switch events tracked in real time
- **SEQI Score** — Composite engagement index (0–100) combining emotion, behavior, distraction, and recovery signals
- **Adaptive Suggestions** — AI-generated nudges via `google/flan-t5-base` when focus dips below threshold
- **Distraction Detection** — Phone detection and idle monitoring with on-screen alerts
- **Session Analytics** — Post-session report with SEQI timeline, emotion distribution, drift detection, recovery analysis
- **Knowledge Quiz** — MCQ quiz generated from video transcript using Ollama (local LLM)
- **Cross-Session Feedback Loop** — Student profiles built over time to pre-adjust pacing and sensitivity

## Tech Stack

| Layer     | Tech                                                        |
|-----------|-------------------------------------------------------------|
| Frontend  | React 19 + Vite + TailwindCSS + Framer Motion + Recharts   |
| Backend   | FastAPI + Python 3.10+                                     |
| ML Models | HuggingFace Transformers (emotion + suggestion) + PyTorch   |
| Database  | Supabase (PostgreSQL) + SQLite (local event logging)        |
| Quiz      | Ollama (local LLM for transcript-based MCQ generation)      |

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

> First run downloads HuggingFace models (~500MB). Wait for "Models ready." in the terminal.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Optional: Quiz (requires Ollama)

```bash
ollama serve
ollama pull llama3.2
```

## Environment Variables

Create `backend/.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
CORS_ORIGINS=http://localhost:5173
```

## Project Structure

```
empath/
├── frontend/          # React + Vite app
│   ├── src/
│   │   ├── pages/     # LandingPage, QuickStartPage, SessionPage, ReportPage, QuizPage, ReportLookupPage
│   │   ├── components/# 13 reusable UI components
│   │   ├── hooks/     # useWebcam
│   │   ├── context/   # SessionContext
│   │   └── api.js     # All API calls
│   └── ...
├── backend/           # FastAPI server
│   ├── main.py        # 15+ API endpoints
│   ├── models/        # emotion_model, suggestion_model, distraction_model
│   ├── services/      # scoring, session, SEQI engine, feedback, quiz, youtube_info
│   ├── database/      # Supabase + SQLite store
│   ├── schemas/       # Pydantic request/response models
│   └── tests/         # pytest tests
└── docs/              # Design docs & plans
```

## Author

Built by **Nithish** for BIS Standards Hackathon 2026.
