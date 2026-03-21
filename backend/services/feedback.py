"""
Feedback Engine — Cross-session learning loop.

After each session, stores:
  - SEQI, emotion pattern, drift segments, quiz score, recovery metrics

On next session, loads previous patterns and:
  - Adjusts suggestion sensitivity
  - Predicts likely disengagement windows
  - Pre-adjusts pacing hints
"""
import logging
from database.sqlite_store import sqlite_store

logger = logging.getLogger(__name__)


class FeedbackEngine:
    """Cross-session feedback and prediction engine."""

    def save_session_feedback(self, session_id: str, student_id: str,
                              analytics: dict, quiz_score: float = None):
        """Save session analytics for future reference."""
        data = {
            "final_seqi": analytics.get("final_seqi", 0),
            "emotion_distribution": analytics.get("emotion_distribution", {}),
            "drift_segments": analytics.get("drift_segments", []),
            "recovery_events": analytics.get("recovery_events", []),
            "key_segments": analytics.get("key_segments", {}),
            "risk_level": analytics.get("risk_level", "red"),
            "total_time": analytics.get("total_time", 0),
            "active_time": analytics.get("active_time", 0),
            "quiz_score": quiz_score,
        }
        sqlite_store.save_feedback(session_id, student_id, data)
        logger.info(f"Saved feedback for session {session_id}, student {student_id}")

    def get_adjustments(self, student_id: str) -> dict:
        """
        Analyze previous session patterns and return adjustments
        for the current session.
        """
        previous = sqlite_store.get_previous_feedback(student_id, limit=5)

        if not previous:
            return {
                "suggestion_sensitivity": 1.0,
                "predicted_disengagement_windows": [],
                "pacing_hints": [],
                "previous_sessions": []
            }

        # Analyze patterns
        avg_seqi = sum(s["final_seqi"] or 0 for s in previous) / len(previous)
        risk_levels = [s["risk_level"] for s in previous]
        all_drifts = []
        for s in previous:
            all_drifts.extend(s.get("drift_segments", []))

        # 1. Adjust suggestion sensitivity
        # If student consistently has low SEQI, be more sensitive (trigger earlier)
        # If consistently high, be less sensitive (don't interrupt)
        if avg_seqi < 40:
            sensitivity = 1.5  # More sensitive — trigger suggestions earlier
        elif avg_seqi < 60:
            sensitivity = 1.2
        elif avg_seqi > 80:
            sensitivity = 0.7  # Less sensitive — student is doing well
        else:
            sensitivity = 1.0

        # 2. Predict disengagement windows
        # Look for common drift timestamps across sessions
        predicted_windows = self._predict_drift_windows(all_drifts)

        # 3. Generate pacing hints
        pacing_hints = self._generate_pacing_hints(previous, avg_seqi)

        return {
            "suggestion_sensitivity": round(sensitivity, 2),
            "predicted_disengagement_windows": predicted_windows,
            "pacing_hints": pacing_hints,
            "previous_sessions": [
                {
                    "session_id": s["session_id"],
                    "seqi": s["final_seqi"],
                    "risk": s["risk_level"],
                    "date": s.get("created_at", "")
                }
                for s in previous[:3]
            ]
        }

    def _predict_drift_windows(self, all_drifts: list) -> list:
        """Identify common drift time windows across sessions."""
        if not all_drifts:
            return []

        # Bucket drift start times into 5-minute windows
        buckets = {}
        for drift in all_drifts:
            if not isinstance(drift, dict):
                continue
            start = drift.get("start", 0)
            bucket = int(start // 300) * 300  # 5-min buckets
            buckets[bucket] = buckets.get(bucket, 0) + 1

        # Return windows with >1 occurrence
        predicted = []
        for bucket_start, count in sorted(buckets.items()):
            if count >= 2:
                predicted.append({
                    "start_seconds": bucket_start,
                    "end_seconds": bucket_start + 300,
                    "likelihood": min(count / 5, 1.0),
                    "label": f"{int(bucket_start//60)}-{int((bucket_start+300)//60)}min"
                })

        return predicted[:3]  # Top 3

    def _generate_pacing_hints(self, previous: list, avg_seqi: float) -> list:
        """Generate pacing hints based on historical patterns."""
        hints = []

        if avg_seqi < 40:
            hints.append("Consider shorter sessions or more frequent breaks.")
            hints.append("Try reducing video speed to 0.75x for complex sections.")

        elif avg_seqi < 60:
            hints.append("Take a short break every 10-15 minutes for better retention.")

        # Check if quiz scores are improving
        quiz_scores = [s.get("quiz_score") for s in previous if s.get("quiz_score") is not None]
        if len(quiz_scores) >= 2:
            if quiz_scores[0] > quiz_scores[-1]:
                hints.append("Your quiz scores are improving — keep up the great work!")
            else:
                hints.append("Try the quiz feature after each session to reinforce learning.")

        # Check recovery patterns
        for s in previous[:2]:
            recoveries = s.get("recovery_metrics", [])
            if isinstance(recoveries, list) and len(recoveries) > 3:
                hints.append("You recover from distractions often — try removing phone from view.")

        return hints[:4]


# Global singleton
feedback_engine = FeedbackEngine()
