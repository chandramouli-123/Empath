from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# ── Request Models ──

class BehaviorEventRequest(BaseModel):
    session_id: str
    event_type: str  # pause | rewind | fast_forward | idle_start | idle_end | play | tab_switch
    timestamp_seconds: float


class ComputeScoreRequest(BaseModel):
    session_id: str
    emotion: str
    confidence: float
    recent_events: List[str]
    timestamp_seconds: float
    is_distracted: bool = False
    distraction_reasons: List[str] = []


class SuggestionRequest(BaseModel):
    session_id: str
    engagement_state: str
    topic: str
    timestamp_seconds: float
    behavioral_summary: Optional[Dict[str, int]] = None
    seqi_trend: float = 0.0


class TabSwitchRequest(BaseModel):
    session_id: str
    timestamp_seconds: float
    is_visible: bool  # True = returned to tab, False = left tab


class QuizSubmitRequest(BaseModel):
    session_id: str
    student_id: str
    answers: List[str]


# ── Response Models ──

class EmotionResponse(BaseModel):
    emotion: str
    confidence: float
    raw_label: str = ""
    phone_detected: bool = False
    distractions: List[str] = []


class ScoreResponse(BaseModel):
    seqi_score: int
    focus_score: int  # backward compat alias for seqi_score
    be: float = 0
    es: float = 0
    id: float = 0
    rr: float = 0
    engagement_state: str
    trend_slope: float = 0
    emotion: str = ""
    is_distracted: bool = False
    distraction_reasons: List[str] = []


class SuggestionResponse(BaseModel):
    suggestion: str
    action: str  # slow_video | speed_up | show_break | nudge | none
    category: str = ""


class AnalyticsResponse(BaseModel):
    session_id: str
    final_seqi: float
    be: float
    es: float
    id: float
    rr: float
    emotion_distribution: Dict[str, float]
    drift_segments: List[Dict]
    recovery_events: List[Dict]
    key_segments: Dict
    risk_level: str
    total_time: float
    active_time: float
    score_timeline: List
    suggestions_given: List[Dict] = []
    behavior_events: List[Dict] = []
    quiz_result: Optional[Dict] = None


class QuizResponse(BaseModel):
    questions: List[Dict[str, str]]
    session_id: str


class QuizGradeResponse(BaseModel):
    scores: List[Dict]
    total_score: float
    session_id: str


class FeedbackResponse(BaseModel):
    suggestion_sensitivity: float = 1.0
    predicted_disengagement_windows: List[Dict] = []
    pacing_hints: List[str] = []
    previous_sessions: List[Dict] = []
