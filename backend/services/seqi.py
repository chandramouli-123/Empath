"""
SEQI — Standardized Engagement Quality Index

SEQI = BE×0.4 + ES×0.3 + ID×0.2 + RR×0.1

Components:
  BE (Behavioral Engagement): active_time / total_time, adjusted for meaningful interactions
  ES (Emotion Stability): 1 - normalized_variance(emotion_transitions) over 60s window
  ID (Interaction Depth): weighted function of rewinds, quiz attempts, pause-reflect patterns
  RR (Recovery Rate): avg time to return to Focused after Distracted/Confused
"""
import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

# SEQI thresholds for engagement state
SEQI_THRESHOLDS = [
    (70, "focused"),
    (45, "confused"),
    (30, "bored"),
    (15, "distressed"),
    (0, "distracted")
]

# Emotion engagement weight multipliers for SEQI
EMOTION_ENGAGEMENT_WEIGHT = {
    "focused": 1.0,
    "neutral": 0.85,
    "confused": 0.58,
    "bored": 0.40,
    "distressed": 0.25,
    "distracted": 0.15,
}

# Emotion class values for stability calculation
EMOTION_VALUES = {
    "focused": 4,
    "neutral": 3,
    "confused": 2,
    "bored": 1,
    "distressed": 0,
    "distracted": 0
}

# Interaction weights for depth calculation
INTERACTION_WEIGHTS = {
    "rewind": 3,
    "quiz_attempt": 5,
    "pause_reflect": 2,  # pause > 2s
    "pause": 1,
    "fast_forward": -1,  # negative — skipping is disengagement
}

SEQI_EMA_ALPHA = 0.18


class SEQIEngine:
    """
    Real-time SEQI calculator. Call update() every analysis cycle (~2s).
    Call finalize() at session end for final scores.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.start_time = time.time()
        self.active_time = 0.0       # seconds of active engagement
        self.total_time = 0.0

        # Emotion history for stability
        self.emotion_history = deque(maxlen=120)  # (timestamp, emotion) — ~2min at 1/s
        self.last_update_time = self.start_time

        # Interaction tracking
        self.interactions = []  # (timestamp, type)
        self.last_elapsed = None
        self._paused_time = 0.0

        # Recovery tracking
        self.recovery_events = []     # (drop_time, recovery_time) pairs
        self._in_recovery = False
        self._recovery_start = None

        # Score history for trend
        self.score_history = deque(maxlen=60)  # (timestamp, seqi)

        # Component cache
        self._last_be = 70
        self._last_es = 80
        self._last_id = 50
        self._last_rr = 80
        self._smoothed_seqi = 72.0

    def update(self, emotion: str, behavior_events: list,
               elapsed_seconds: float, is_distracted: bool = False,
               confidence: float = 1.0) -> dict:
        """
        Update SEQI with current frame data.
        Returns full SEQI breakdown.
        """
        # Determine dt from elapsed_seconds when advancing, fallback to wall clock
        if hasattr(self, "last_elapsed") and self.last_elapsed is not None:
            dt = max(0.0, elapsed_seconds - self.last_elapsed)
        else:
            now = time.time()
            dt = min(2.0, max(0.5, now - getattr(self, "last_update_time", now)))
            self.last_update_time = now

        if dt >= 10:
            # The frontend pauses video and stops score submissions while the
            # face is absent. Exclude that wall-clock gap from active SEQI time
            # instead of turning it into a delayed BE collapse on return.
            self._paused_time += dt

        self.last_elapsed = elapsed_seconds
        self.total_time = max(elapsed_seconds - self._paused_time, 1.0)

        # Facial emotion remains the user's authentic facial expression
        effective_emotion = str(emotion or "focused").lower()
        confidence = max(0.0, min(1.0, float(confidence)))

        # Track emotion for stability analysis
        self.emotion_history.append((elapsed_seconds, effective_emotion))

        # Track active time (give 50% credit during background checks so score doesn't freefall)
        if 0 < dt < 10:
            if not is_distracted:
                self.active_time += dt
            else:
                self.active_time += dt * 0.5

        self.active_time = min(self.active_time, self.total_time)

        # Track interactions
        for event in behavior_events:
            self.interactions.append((elapsed_seconds, event))

        # Track recovery
        self._track_recovery(elapsed_seconds, effective_emotion)

        # Compute components
        be = self._compute_behavioral_engagement()
        es = self._compute_emotion_stability()
        id_score = self._compute_interaction_depth()
        rr = self._compute_recovery_rate()

        self._last_be = be
        self._last_es = es
        self._last_id = id_score
        self._last_rr = rr

        # SEQI formula with Emotional Engagement Multiplier & EMA smoothing
        component_base = be * 0.4 + es * 0.3 + id_score * 0.2 + rr * 0.1
        emotion_key = "distracted" if is_distracted else effective_emotion.lower()
        multiplier = EMOTION_ENGAGEMENT_WEIGHT.get(emotion_key, 0.85)
        if not is_distracted and emotion_key not in ("focused", "neutral"):
            # Do not apply a full penalty to an uncertain facial prediction.
            # Full weight is reached at 0.60 confidence, matching the local
            # emotion model's high-conviction threshold.
            confidence_factor = min(
                1.0,
                max(0.0, (confidence - 0.25) / (0.60 - 0.25))
            )
            multiplier = 1.0 - ((1.0 - multiplier) * confidence_factor)
        raw_seqi = int(component_base * multiplier)
        raw_seqi = max(0, min(100, raw_seqi))

        if hasattr(self, "_smoothed_seqi") and self._smoothed_seqi is not None:
            smoothing_alpha = 0.45 if is_distracted else SEQI_EMA_ALPHA
            self._smoothed_seqi = (
                (1 - smoothing_alpha) * self._smoothed_seqi
                + smoothing_alpha * raw_seqi
            )
        else:
            self._smoothed_seqi = float(raw_seqi)

        seqi = int(round(self._smoothed_seqi))

        # Track score for trend
        self.score_history.append((elapsed_seconds, seqi))

        # Engagement state from SEQI or behavioral distraction
        if is_distracted:
            engagement_state = "distracted"
        else:
            engagement_state = "focused"
            for threshold, state in SEQI_THRESHOLDS:
                if seqi >= threshold:
                    engagement_state = state
                    break

        return {
            "seqi_score": seqi,
            "be": round(be, 1),
            "es": round(es, 1),
            "id": round(id_score, 1),
            "rr": round(rr, 1),
            "engagement_state": engagement_state,
            "trend_slope": self._compute_trend_slope(),
            "emotion": effective_emotion,
            # Backward compat
            "focus_score": seqi,
        }

    def finalize(self) -> dict:
        """Compute final session-level SEQI with averages."""
        if not self.score_history:
            return self._empty_result()

        scores = [s for _, s in self.score_history]
        avg_seqi = round(sum(scores) / len(scores), 1)

        # Emotion distribution
        emotion_counts = {}
        for _, em in self.emotion_history:
            emotion_counts[em] = emotion_counts.get(em, 0) + 1
        total = sum(emotion_counts.values()) or 1

        # Cognitive drift segments: SEQI declining for >15s
        drift_segments = self._detect_drift_segments()

        # Best/worst segments
        segments = self._detect_key_segments()

        return {
            "final_seqi": avg_seqi,
            "be": round(self._last_be, 1),
            "es": round(self._last_es, 1),
            "id": round(self._last_id, 1),
            "rr": round(self._last_rr, 1),
            "emotion_distribution": {
                em: round(count / total * 100, 1)
                for em, count in emotion_counts.items()
            },
            "drift_segments": drift_segments,
            "recovery_events": [
                {"drop_at": d, "recovered_at": r, "duration": round(r - d, 1)}
                for d, r in self.recovery_events
            ],
            "key_segments": segments,
            "risk_level": "green" if avg_seqi >= 70 else "yellow" if avg_seqi >= 40 else "red",
            "total_time": round(self.total_time, 1),
            "active_time": round(self.active_time, 1),
            "score_timeline": list(self.score_history),
        }

    # ── Component Calculations ──

    def _compute_behavioral_engagement(self) -> float:
        """Active time / total time, adjusted for meaningful interactions."""
        if self.total_time < 1:
            return 70.0

        base = (self.active_time / self.total_time) * 100

        # Bonus for meaningful interactions in last 60s
        now_ts = self.emotion_history[-1][0] if self.emotion_history else 0
        recent = [t for t, ev in self.interactions if now_ts - t < 60]
        meaningful = sum(1 for t, ev in self.interactions
                        if now_ts - t < 60 and ev in ("rewind", "pause"))
        bonus = min(meaningful * 3, 15)

        return max(0, min(100, base + bonus))

    def _compute_emotion_stability(self) -> float:
        """1 - normalized_variance(emotion_transitions) over 60s window."""
        if len(self.emotion_history) < 3:
            return 80.0

        # Get last 60s of emotions
        now_ts = self.emotion_history[-1][0]
        recent = [EMOTION_VALUES.get(em, 2)
                  for ts, em in self.emotion_history if now_ts - ts < 60]

        if len(recent) < 2:
            return 80.0

        # Count transitions (emotion changes)
        transitions = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        max_transitions = len(recent) - 1

        # Variance of emotion values
        mean = sum(recent) / len(recent)
        variance = sum((v - mean) ** 2 for v in recent) / len(recent)
        max_variance = 4.0  # max possible variance with values 0-4

        # Normalize: low transitions + low variance = high stability
        transition_factor = 1 - (transitions / max(max_transitions, 1))
        variance_factor = 1 - (variance / max_variance)

        stability = (transition_factor * 0.6 + variance_factor * 0.4) * 100
        return max(0, min(100, stability))

    def _compute_interaction_depth(self) -> float:
        """Weighted function of intentional rewinds, quiz attempts, pause-reflect patterns."""
        if not self.interactions:
            return 40.0  # baseline

        weighted_sum = 0
        for ts, event in self.interactions:
            weight = INTERACTION_WEIGHTS.get(event, 0)
            weighted_sum += weight

        # Normalize: expect ~10 meaningful interactions per 5min session
        expected = max(self.total_time / 30, 1)  # 1 interaction per 30s
        normalized = (weighted_sum / expected) * 50 + 40  # center around 40-90

        return max(0, min(100, normalized))

    def _compute_recovery_rate(self) -> float:
        """Average time to return to Focused after Distracted/Confused."""
        if not self.recovery_events:
            return 80.0  # no drops = good

        avg_recovery = sum(r - d for d, r in self.recovery_events) / len(self.recovery_events)
        # Lower recovery time = better score
        # 0s recovery → 100, 30s → 40, 60s+ → 0
        score = 100 - (avg_recovery * 2)
        return max(0, min(100, score))

    def _track_recovery(self, timestamp: float, emotion: str):
        """Track recovery events: time from drop to focused."""
        if emotion in ("distracted", "confused", "bored", "distressed"):
            if not self._in_recovery:
                self._in_recovery = True
                self._recovery_start = timestamp
        elif emotion == "focused" and self._in_recovery:
            if self._recovery_start is not None:
                self.recovery_events.append((self._recovery_start, timestamp))
            self._in_recovery = False
            self._recovery_start = None

    def _compute_trend_slope(self) -> float:
        """SEQI trend over last 30s. Positive = improving, negative = declining."""
        if len(self.score_history) < 3:
            return 0.0

        recent = [(t, s) for t, s in self.score_history
                  if self.score_history[-1][0] - t < 30]

        if len(recent) < 2:
            return 0.0

        # Simple linear regression slope
        n = len(recent)
        sum_t = sum(t for t, s in recent)
        sum_s = sum(s for t, s in recent)
        sum_ts = sum(t * s for t, s in recent)
        sum_t2 = sum(t * t for t, s in recent)

        denom = n * sum_t2 - sum_t ** 2
        if abs(denom) < 0.001:
            return 0.0

        slope = (n * sum_ts - sum_t * sum_s) / denom
        return round(slope, 2)

    def _detect_drift_segments(self) -> list:
        """Find segments where SEQI was declining for >15 consecutive seconds."""
        if len(self.score_history) < 5:
            return []

        segments = []
        drift_start = None
        prev_score = None

        for ts, score in self.score_history:
            if prev_score is not None and score < prev_score:
                if drift_start is None:
                    drift_start = ts
            else:
                if drift_start is not None and prev_score is not None:
                    duration = ts - drift_start
                    if duration > 15:
                        segments.append({
                            "start": round(drift_start, 1),
                            "end": round(ts, 1),
                            "duration": round(duration, 1),
                            "score_drop": round(self.score_history[0][1] - score, 1)
                        })
                drift_start = None
            prev_score = score

        return segments

    def _detect_key_segments(self) -> dict:
        """Find most focused, most distracted, most confusing segments."""
        if not self.score_history:
            return {}

        # Simple: find min/max score timestamps
        scores = list(self.score_history)
        if not scores:
            return {}

        max_score = max(scores, key=lambda x: x[1])
        min_score = min(scores, key=lambda x: x[1])

        # Find most confusing segment (longest period of confused emotion)
        confused_start = None
        longest_confused = (0, 0)
        for ts, em in self.emotion_history:
            if em == "confused":
                if confused_start is None:
                    confused_start = ts
            else:
                if confused_start is not None:
                    duration = ts - confused_start
                    if duration > longest_confused[1] - longest_confused[0]:
                        longest_confused = (confused_start, ts)
                confused_start = None

        return {
            "most_focused": {"timestamp": max_score[0], "score": max_score[1]},
            "most_distracted": {"timestamp": min_score[0], "score": min_score[1]},
            "most_confusing": {
                "start": longest_confused[0],
                "end": longest_confused[1],
                "duration": round(longest_confused[1] - longest_confused[0], 1)
            }
        }

    def _empty_result(self) -> dict:
        return {
            "final_seqi": 0, "be": 0, "es": 0, "id": 0, "rr": 0,
            "emotion_distribution": {},
            "drift_segments": [], "recovery_events": [], "key_segments": {},
            "risk_level": "red", "total_time": 0, "active_time": 0,
            "score_timeline": []
        }


def get_behavioral_summary(events: list, window_seconds: float = 60) -> dict:
    """
    Summarize behavior events for the suggestion model.
    Returns counts of each event type in the window.
    """
    counts = {}
    for event in events:
        counts[event] = counts.get(event, 0) + 1

    return {
        "rewinds": counts.get("rewind", 0),
        "pauses": counts.get("pause", 0),
        "fast_forwards": counts.get("fast_forward", 0),
        "idles": counts.get("idle_start", 0),
        "phone_detections": counts.get("phone_detected", 0),
        "tab_switches": counts.get("tab_switch", 0),
        "total_events": len(events)
    }
