from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from models import emotion_model, suggestion_model, distraction_model, gemini_emotion
from services import scoring, session as session_service
from services.seqi import SEQIEngine, get_behavioral_summary
from services.distraction_detector import DistractionDetector
from services.feedback import feedback_engine
from services import quiz as quiz_service
from services.youtube_info import get_video_info as fetch_video_info
from database.sqlite_store import sqlite_store
from schemas.schemas import (
    BehaviorEventRequest, ComputeScoreRequest,
    SuggestionRequest, TabSwitchRequest, QuizSubmitRequest,
    EmotionResponse, ScoreResponse, SuggestionResponse,
    AnalyticsResponse, QuizResponse, QuizGradeResponse, FeedbackResponse
)

models_ready = False

# Per-session state (in-memory, keyed by session_id)
# In production, this would be in Redis or similar
session_state = {}
_session_metadata = {}


def _get_session_state(session_id: str) -> dict:
    """Get or create per-session state for SEQI + distraction tracking."""
    if session_id not in session_state:
        session_state[session_id] = {
            "seqi": SEQIEngine(),
            "distraction": DistractionDetector(),
            "video_url": "",
            "topic": "",
            "student_id": "student_001",
        }
    return session_state[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global models_ready
    print("Loading facial emotion model...")
    try:
        emotion_model.load_model()
        print("Facial emotion model loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load facial emotion model: {e}")

    models_ready = True
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──

@app.get("/api/health")
@app.get("/health")
def health():
    return {"models_ready": models_ready}


@app.get("/api/video-info")
def video_info(url: str = ""):
    """Fetch YouTube video metadata: title, description, chapters."""
    if not url:
        return {"title": "", "description": "", "chapters": [], "duration": 0}
    try:
        return fetch_video_info(url)
    except Exception as e:
        logger.error(f"video-info failed: {e}")
        return {"title": "", "description": "", "chapters": [], "duration": 0}


# ── Session Management ──

@app.post("/api/start-session")
def start_session(
    student_id: str = "student_001",
    video_id: str = "video_001",
    topic: str = "General",
    video_url: str = ""
):
    session_id = session_service.create_session(student_id, video_id, topic)

    # Initialize session state
    state = _get_session_state(session_id)
    state["topic"] = topic
    state["video_url"] = video_url
    state["student_id"] = student_id
    _session_metadata[session_id] = {
        "topic": topic,
        "video_url": video_url,
        "student_id": student_id
    }

    # Load feedback from previous sessions
    adjustments = feedback_engine.get_adjustments(student_id)

    return {
        "session_id": session_id,
        "feedback_adjustments": adjustments
    }


@app.post("/api/end-session/{session_id}")
def end_session(session_id: str):
    state = _get_session_state(session_id)

    # Finalize SEQI
    analytics = state["seqi"].finalize()

    # Save feedback for cross-session loop
    feedback_engine.save_session_feedback(
        session_id, state["student_id"], analytics
    )

    # End in Supabase
    session_service.end_session(session_id)

    # Cleanup
    session_state.pop(session_id, None)

    return {"ended": True, "final_seqi": analytics.get("final_seqi", 0)}


# ── Emotion Analysis ──

@app.post("/api/analyze-emotion", response_model=EmotionResponse)
async def analyze_emotion(file: UploadFile = File(...)):
    if not models_ready:
        raise HTTPException(status_code=503, detail="Models still loading")
    try:
        image_bytes = await file.read()

        # Check if Gemini Vision backend is enabled and key is present
        gemini_result = None
        use_gemini = os.environ.get("EMOTION_BACKEND", "").lower() != "local" and gemini_emotion.is_gemini_available()
        if use_gemini:
            gemini_result = gemini_emotion.analyze_with_gemini(image_bytes)

        if gemini_result:
            return gemini_result

        # Local model baseline (fast, offline, private)
        result = emotion_model.analyze_frame(image_bytes)
        distraction_result = distraction_model.detect_distractions(image_bytes)
        result.update(distraction_result)
        return result
    except Exception as e:
        logger.error(f"[analyze-emotion] Error: {e}")
        return {
            "emotion": "focused",
            "confidence": 0.0,
            "raw_label": "error",
            "phone_detected": False,
            "distractions": []
        }


# ── Behavior Events ──

@app.post("/api/behavior-event")
def behavior_event(req: BehaviorEventRequest):
    state = _get_session_state(req.session_id)

    # Record activity for distraction detector
    state["distraction"].record_activity(req.timestamp_seconds)

    session_service.save_behavior_event(
        req.session_id, req.timestamp_seconds, req.event_type
    )
    return {"received": True}


@app.post("/api/tab-switch")
def tab_switch(req: TabSwitchRequest):
    state = _get_session_state(req.session_id)

    if not req.is_visible:
        # User left the tab
        state["distraction"].record_tab_switch(req.timestamp_seconds)
        session_service.save_behavior_event(
            req.session_id, req.timestamp_seconds, "tab_switch"
        )

    return {"received": True}


# ── SEQI Score Computation ──

@app.post("/api/compute-score", response_model=ScoreResponse)
def compute_score(req: ComputeScoreRequest):
    state = _get_session_state(req.session_id)

    # Check distraction
    distraction_result = state["distraction"].detect(req.timestamp_seconds)
    is_distracted = req.is_distracted or distraction_result["is_distracted"]

    # Record focus score for distraction detector
    # (uses old scoring for backward compat input)
    old_result = scoring.compute_focus_score(req.emotion, req.recent_events)
    state["distraction"].record_focus_score(req.timestamp_seconds, old_result["focus_score"])

    # Update SEQI
    seqi_result = state["seqi"].update(
        emotion=req.emotion,
        behavior_events=req.recent_events,
        elapsed_seconds=req.timestamp_seconds,
        is_distracted=is_distracted
    )

    # Log to SQLite
    sqlite_store.log_event(req.session_id, req.timestamp_seconds, {
        **seqi_result,
        "behavior_events": req.recent_events,
        "is_distracted": is_distracted,
        "distraction_reasons": distraction_result["reasons"]
    })

    # Save emotion event to Supabase
    session_service.save_emotion_event(
        req.session_id,
        req.timestamp_seconds,
        seqi_result["emotion"],
        req.confidence,
        seqi_result["seqi_score"]
    )

    return {
        **seqi_result,
        "is_distracted": is_distracted,
        "distraction_reasons": distraction_result["reasons"]
    }


# ── Suggestions ──

@app.post("/api/get-suggestion", response_model=SuggestionResponse)
def get_suggestion(req: SuggestionRequest):
    result = suggestion_model.generate_suggestion(
        emotion=req.engagement_state,
        topic=req.topic,
        behavioral_summary=req.behavioral_summary or {},
        seqi_trend=req.seqi_trend,
        video_timestamp=req.timestamp_seconds
    )

    if result["suggestion"]:
        session_service.save_suggestion(
            req.session_id,
            req.timestamp_seconds,
            req.engagement_state,
            result["suggestion"],
            result["action"]
        )

    return result


# ── Session Analytics ──

@app.get("/api/session-timeline/{session_id}")
def session_timeline(session_id: str):
    return sqlite_store.get_session_timeline(session_id)


@app.get("/api/session-analytics/{session_id}")
def session_analytics(session_id: str):
    """Full post-session analytics combining Supabase + SQLite data."""
    try:
        return _build_analytics(session_id)
    except Exception as e:
        logger.error(f"Analytics failed for {session_id}: {e}")
        return {
            "session_id": session_id,
            "final_seqi": 0, "be": 0, "es": 0, "id": 0, "rr": 0,
            "emotion_distribution": {},
            "drift_segments": [], "recovery_events": [], "key_segments": {},
            "risk_level": "yellow",
            "total_time": 0, "active_time": 0,
            "score_timeline": [],
            "suggestions_given": [], "behavior_events": [],
            "quiz_result": None
        }


def _build_analytics(session_id: str) -> dict:
    """Build analytics from Supabase + SQLite."""
    # Get Supabase data
    report = session_service.get_session_report(session_id)

    # Get SQLite timeline
    timeline = sqlite_store.get_session_timeline(session_id)

    # Get quiz result if exists
    quiz_result = sqlite_store.get_quiz_result(session_id)

    # Compute final analytics from timeline
    if timeline:
        scores = [p["seqi"] for p in timeline if p["seqi"]]
        avg_seqi = sum(scores) / len(scores) if scores else 0

        # Emotion distribution
        emotion_counts = {}
        for p in timeline:
            em = p["emotion"]
            emotion_counts[em] = emotion_counts.get(em, 0) + 1
        total = sum(emotion_counts.values()) or 1
        emotion_dist = {em: round(c / total * 100, 1) for em, c in emotion_counts.items()}

        # Drift segments (declining SEQI for >15s)
        drift_segments = _detect_drift(timeline)

        # Recovery events
        recovery_events = _detect_recovery(timeline)

        # Key segments
        key_segments = _detect_segments(timeline)

        # Risk level
        risk = "green" if avg_seqi >= 70 else "yellow" if avg_seqi >= 40 else "red"

        total_time = timeline[-1]["t"] if timeline else 0

        return {
            "session_id": session_id,
            "final_seqi": round(avg_seqi, 1),
            "be": timeline[-1].get("be", 0) if timeline else 0,
            "es": timeline[-1].get("es", 0) if timeline else 0,
            "id": timeline[-1].get("id", 0) if timeline else 0,
            "rr": timeline[-1].get("rr", 0) if timeline else 0,
            "emotion_distribution": emotion_dist,
            "drift_segments": drift_segments,
            "recovery_events": recovery_events,
            "key_segments": key_segments,
            "risk_level": risk,
            "total_time": total_time,
            "active_time": total_time * 0.8,  # estimate
            "score_timeline": [{"t": p["t"], "seqi": p["seqi"], "emotion": p["emotion"]} for p in timeline],
            "suggestions_given": report.get("suggestions_given", []),
            "behavior_events": report.get("behavior_events", []),
            "quiz_result": quiz_result
        }

    # Fallback to Supabase report
    focus_timeline = report.get("focus_timeline", [])
    # Normalize keys: Supabase stores 'score', frontend expects 'seqi'
    normalized_timeline = [
        {"t": p.get("t", p.get("timestamp_seconds", 0)),
         "seqi": p.get("seqi", p.get("score", p.get("focus_score", 50))),
         "emotion": p.get("emotion", "focused")}
        for p in focus_timeline
    ]

    supabase_total_time = normalized_timeline[-1]["t"] if normalized_timeline else 0

    # Compute emotion distribution from Supabase data
    emotion_dist = report.get("emotion_distribution", {})
    if isinstance(emotion_dist, dict) and emotion_dist:
        total_count = sum(emotion_dist.values()) or 1
        # If counts are raw numbers, convert to percentages
        if any(v > 100 for v in emotion_dist.values()):
            emotion_dist = {k: round(v / total_count * 100, 1) for k, v in emotion_dist.items()}

    avg_score = report.get("average_focus_score", 0)
    risk = "green" if avg_score >= 70 else "yellow" if avg_score >= 40 else "red"

    return {
        "session_id": session_id,
        "final_seqi": avg_score,
        "be": 0, "es": 0, "id": 0, "rr": 0,
        "emotion_distribution": emotion_dist,
        "drift_segments": [],
        "recovery_events": [],
        "key_segments": {},
        "risk_level": risk,
        "total_time": supabase_total_time, "active_time": supabase_total_time * 0.8,
        "score_timeline": normalized_timeline,
        "suggestions_given": report.get("suggestions_given", []),
        "behavior_events": report.get("behavior_events", []),
        "quiz_result": quiz_result
    }


@app.get("/api/session-report/{session_id}")
def session_report(session_id: str):
    """Backward-compatible report endpoint."""
    return session_service.get_session_report(session_id)


# ── Quiz ──

# Cache generated questions per session (so submit can access them)
_quiz_cache = {}


@app.post("/api/quiz/generate/{session_id}")
def generate_quiz(session_id: str):
    """Generate MCQ quiz from video transcript using Ollama or intelligent topic generator."""
    meta = _session_metadata.get(session_id, {})
    state = session_state.get(session_id, meta)
    video_url = state.get("video_url") or meta.get("video_url", "")
    topic = state.get("topic") or meta.get("topic", "Machine Learning")

    transcript = quiz_service.fetch_transcript(video_url) if video_url else ""
    questions = quiz_service.generate_quiz(transcript, topic)

    # Cache for submit
    _quiz_cache[session_id] = questions

    return {"questions": questions, "session_id": session_id}


@app.post("/api/quiz/submit/{session_id}")
def submit_quiz(session_id: str, req: QuizSubmitRequest):
    """Submit MCQ answers for grading."""
    # Get cached questions
    questions = _quiz_cache.get(session_id, [])

    if not questions:
        # Try regenerating using stored metadata
        meta = _session_metadata.get(session_id, {})
        state = session_state.get(session_id, meta)
        video_url = state.get("video_url") or meta.get("video_url", "")
        topic = state.get("topic") or meta.get("topic", "Machine Learning")
        transcript = quiz_service.fetch_transcript(video_url) if video_url else ""
        questions = quiz_service.generate_quiz(transcript, topic)

    # Grade MCQ answers
    result = quiz_service.grade_answers(questions, req.answers)

    # Save to SQLite
    sqlite_store.save_quiz_result(
        session_id, req.student_id,
        questions, req.answers,
        result["scores"], result["total_score"]
    )

    # Update feedback
    feedback_engine.save_session_feedback(
        session_id, req.student_id,
        {"quiz_score": result["total_score"]}
    )

    # Cleanup cache
    _quiz_cache.pop(session_id, None)

    return {
        "scores": result["scores"],
        "total_score": result["total_score"],
        "session_id": session_id
    }


# ── Feedback ──

@app.get("/api/feedback/{student_id}")
def get_feedback(student_id: str):
    """Get cross-session feedback adjustments."""
    return feedback_engine.get_adjustments(student_id)


# ── Helpers ──

def _detect_drift(timeline: list) -> list:
    """Find declining SEQI segments >15s."""
    segments = []
    drift_start = None
    prev_score = None
    for p in timeline:
        score = p["seqi"]
        if prev_score is not None and score < prev_score:
            if drift_start is None:
                drift_start = p["t"]
        else:
            if drift_start is not None:
                duration = p["t"] - drift_start
                if duration > 15:
                    segments.append({
                        "start": drift_start, "end": p["t"],
                        "duration": round(duration, 1)
                    })
            drift_start = None
        prev_score = score
    return segments


def _detect_recovery(timeline: list) -> list:
    """Find recovery events (distracted/confused → focused)."""
    events = []
    in_drop = False
    drop_start = None
    for p in timeline:
        if p["emotion"] in ("distracted", "confused", "distressed"):
            if not in_drop:
                in_drop = True
                drop_start = p["t"]
        elif p["emotion"] == "focused" and in_drop:
            events.append({
                "drop_at": drop_start, "recovered_at": p["t"],
                "duration": round(p["t"] - drop_start, 1)
            })
            in_drop = False
    return events


def _detect_segments(timeline: list) -> dict:
    """Find most focused/distracted/confusing segments."""
    if not timeline:
        return {}
    best = max(timeline, key=lambda p: p["seqi"])
    worst = min(timeline, key=lambda p: p["seqi"])
    return {
        "most_focused": {"timestamp": best["t"], "score": best["seqi"]},
        "most_distracted": {"timestamp": worst["t"], "score": worst["seqi"]},
    }
