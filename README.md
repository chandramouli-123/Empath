# Empath

Empath is an emotion-aware learning assistant for YouTube-based study sessions. It combines webcam signals, playback behavior, distraction detection, and session history to estimate engagement while a learner watches a video.

## What It Does

- Captures a webcam frame every two seconds during an active session.
- Detects face presence and maps facial signals to `focused`, `neutral`, `confused`, `bored`, `distressed`, or `distracted` states.
- Detects distraction signals such as phone presence, idle time, repeated focus drops, and tab switches.
- Calculates a smoothed SEQI score from Behavioral Engagement, Emotion Stability, Interaction Depth, and Recovery Rate.
- Provides adaptive suggestions when engagement falls.
- Fetches YouTube metadata and chapters for the session video.
- Generates a four-question transcript-grounded quiz with three conceptual questions and one applied question.
- Produces a session report with score timeline, emotion distribution, heatmap, drift segments, recovery events, risk level, and quiz results.
- Uses previous session feedback to adjust suggestion sensitivity and provide pacing hints.

## Architecture

### Frontend

The React 19 and Vite frontend provides the learner workflow:

| Route | Purpose |
| --- | --- |
| `/` | Landing page and product overview |
| `/start` | Create a session from a learner name, topic, and YouTube URL |
| `/session` | Watch the video and see live emotion, distraction, SEQI, and suggestion signals |
| `/report/:sessionId` | Review session analytics |
| `/quiz/:sessionId` | Generate and submit the post-session quiz |
| `/report-lookup` | Open a previous report by session ID |

The main frontend technologies are React, React Router, Axios, Tailwind CSS, Framer Motion, Recharts, and `react-youtube`.

### Backend

The FastAPI backend owns session state and analysis:

- `models/emotion_model.py`: local facial emotion and face-presence analysis.
- `models/gemini_emotion.py`: optional Gemini Vision analysis with local fallback.
- `models/distraction_model.py`: object detection and phone detection.
- `models/suggestion_model.py`: adaptive learning suggestions.
- `services/seqi.py`: real-time SEQI calculation with EMA smoothing.
- `services/distraction_detector.py`: behavioral distraction rules.
- `services/quiz.py`: transcript retrieval, quiz generation, and fallback questions.
- `services/youtube_info.py`: YouTube metadata and chapter extraction.
- `services/feedback.py`: cross-session feedback and pacing adjustments.
- `database/db.py`: optional Supabase client.
- `database/sqlite_store.py`: local event, feedback, and quiz storage.
- `schemas/schemas.py`: request and response models.

The API includes health checks, session management, emotion analysis, behavior and tab-switch events, SEQI scoring, suggestions, analytics, quizzes, and feedback endpoints under `/api`.

## Data and Model Modes

By default, facial analysis uses the local Hugging Face model and OpenCV/Mediapipe face checks. If `EMOTION_BACKEND=gemini` and `GEMINI_API_KEY` are configured, Gemini Vision may be used for emotion analysis; the backend falls back to the local model when Gemini is unavailable.

Supabase stores session-level records when configured. SQLite stores detailed local timelines and feedback in `backend/empath_local.db`. The database file is intentionally ignored by Git and is created automatically when the backend runs.

## Setup

### Backend

Python 3.10 or newer is recommended.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

The first startup may download the Hugging Face models used for emotion and object detection. To start the API without loading those models during a lightweight test or frontend-only session, use `SKIP_MODELS=true`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend expects the backend at `http://localhost:8000`.

## Environment Variables

Create `backend/.env` from [`backend/.env.example`](backend/.env.example):

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
CORS_ORIGINS=http://localhost:5173
```

Optional settings:

```dotenv
EMOTION_BACKEND=local
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-3.8-flash
SKIP_MODELS=false
```

Do not commit `.env`, API keys, model caches, local databases, or generated reports.

## Testing and Build Checks

Run backend tests from `backend/`:

```bash
pytest tests
```

Build and lint the frontend from `frontend/`:

```bash
npm run lint
npm run build
```

## Repository Layout

```text
Empath/
├── backend/
│   ├── main.py
│   ├── models/
│   ├── services/
│   ├── database/
│   ├── schemas/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── hooks/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

Rollback scripts and local backup copies are intentionally kept out of the GitHub repository.
