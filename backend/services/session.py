import logging
import uuid
from datetime import datetime, timezone
from database.db import supabase

logger = logging.getLogger(__name__)


def create_session(student_id: str, video_id: str, topic: str) -> str:
    if supabase:
        try:
            result = supabase.table("sessions").insert({
                "student_id": student_id,
                "video_id": video_id,
                "topic": topic
            }).execute()
            if result.data and len(result.data) > 0:
                return str(result.data[0]["id"])
        except Exception as e:
            logger.warning(f"Supabase create_session failed: {e}. Falling back to local UUID.")

    return str(uuid.uuid4())


def save_emotion_event(session_id, timestamp_seconds, emotion, confidence, focus_score):
    if not supabase:
        return
    try:
        supabase.table("emotion_events").insert({
            "session_id": session_id,
            "timestamp_seconds": timestamp_seconds,
            "emotion": emotion,
            "confidence": confidence,
            "focus_score": focus_score
        }).execute()
    except Exception as e:
        logger.warning(f"Supabase save_emotion_event failed: {e}")


def save_behavior_event(session_id, timestamp_seconds, event_type):
    if not supabase:
        return
    try:
        supabase.table("behavior_events").insert({
            "session_id": session_id,
            "timestamp_seconds": timestamp_seconds,
            "event_type": event_type
        }).execute()
    except Exception as e:
        logger.warning(f"Supabase save_behavior_event failed: {e}")


def save_suggestion(session_id, timestamp_seconds, engagement_state, suggestion_text, action):
    if not supabase:
        return
    try:
        supabase.table("suggestions").insert({
            "session_id": session_id,
            "timestamp_seconds": timestamp_seconds,
            "engagement_state": engagement_state,
            "suggestion_text": suggestion_text,
            "action": action
        }).execute()
    except Exception as e:
        logger.warning(f"Supabase save_suggestion failed: {e}")


def get_session_report(session_id: str) -> dict:
    emotions = []
    behaviors = []
    suggestions = []
    if supabase:
        try:
            emotions = supabase.table("emotion_events") \
                .select("*").eq("session_id", session_id) \
                .order("timestamp_seconds").execute().data or []
            behaviors = supabase.table("behavior_events") \
                .select("*").eq("session_id", session_id) \
                .order("timestamp_seconds").execute().data or []
            suggestions = supabase.table("suggestions") \
                .select("*").eq("session_id", session_id) \
                .order("timestamp_seconds").execute().data or []
        except Exception as e:
            logger.warning(f"Supabase get_session_report failed: {e}")

    avg_score = (
        sum(e["focus_score"] for e in emotions) / len(emotions)
        if emotions else 0
    )

    emotion_counts = {}
    for e in emotions:
        emotion_counts[e["emotion"]] = emotion_counts.get(e["emotion"], 0) + 1

    return {
        "session_id": session_id,
        "average_focus_score": round(avg_score, 1),
        "emotion_distribution": emotion_counts,
        "focus_timeline": [
            {"t": e["timestamp_seconds"], "score": e["focus_score"], "emotion": e["emotion"]}
            for e in emotions
        ],
        "behavior_events": behaviors,
        "suggestions_given": suggestions,
        "total_events": len(behaviors)
    }


def end_session(session_id: str):
    if not supabase:
        return
    try:
        supabase.table("sessions").update({
            "ended_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", session_id).execute()
    except Exception as e:
        logger.warning(f"Supabase end_session failed: {e}")

