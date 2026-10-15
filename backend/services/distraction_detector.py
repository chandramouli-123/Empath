"""
Distraction Detector — infers 'distracted' state from behavioral signals.
This is NOT a model prediction. It's derived from:
  - Idle time > 30 seconds
  - Tab switching
  - Repeated focus loss patterns (≥3 drops below 50 in 60s)
  - Sudden behavioral engagement drop (>30 points in 10s)
"""
import time
import logging

logger = logging.getLogger(__name__)

# Thresholds
IDLE_THRESHOLD_SECONDS = 45
TAB_SWITCH_THRESHOLD = 4          # tab switches in 20s window
FOCUS_DROP_THRESHOLD = 4          # focus drops below 50 in 60s window
BEHAVIOR_DROP_THRESHOLD = 30      # points drop in 10s


class DistractionDetector:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last_activity_elapsed = 0.0
        self.tab_switches = []          # timestamps of tab switches (elapsed seconds)
        self.focus_drops = []           # timestamps of focus drops below 50
        self.behavior_scores = []       # (timestamp, score) pairs
        self.idle_detected = False

    def record_activity(self, timestamp: float = None):
        """Call when user interacts (mouse, keyboard, video control)."""
        if timestamp is not None:
            self.last_activity_elapsed = timestamp
        self.idle_detected = False

    def record_tab_switch(self, timestamp: float):
        """Call when tab visibility changes."""
        self.tab_switches.append(timestamp)

    def record_focus_score(self, timestamp: float, score: int):
        """Call after each SEQI/focus score computation."""
        self.behavior_scores.append((timestamp, score))
        if score < 50:
            self.focus_drops.append(timestamp)

    def detect(self, current_time: float = 0.0) -> dict:
        """
        Evaluate all distraction signals and return result.
        Returns { is_distracted: bool, reasons: list[str] }
        """
        now = current_time
        reasons = []

        # 1. Idle detection based on session elapsed time
        idle_seconds = max(0.0, now - self.last_activity_elapsed) if self.last_activity_elapsed > 0 else 0.0
        if idle_seconds > IDLE_THRESHOLD_SECONDS:
            reasons.append(f"idle_{int(idle_seconds)}s")
            self.idle_detected = True

        # 2. Tab switches in last 20s
        recent_tab_switches = [t for t in self.tab_switches if now - t < 20]
        self.tab_switches = recent_tab_switches  # prune old
        if len(recent_tab_switches) >= TAB_SWITCH_THRESHOLD:
            reasons.append(f"tab_switches_{len(recent_tab_switches)}")

        # 3. Repeated focus drops in last 60s
        recent_drops = [t for t in self.focus_drops if now - t < 60]
        self.focus_drops = recent_drops  # prune old
        if len(recent_drops) >= FOCUS_DROP_THRESHOLD:
            reasons.append(f"focus_drops_{len(recent_drops)}")

        # 4. Sudden behavioral engagement drop in last 10s
        recent_scores = [(t, s) for t, s in self.behavior_scores if now - t < 10]
        self.behavior_scores = [(t, s) for t, s in self.behavior_scores if now - t < 120]
        if len(recent_scores) >= 2:
            oldest_score = recent_scores[0][1]
            newest_score = recent_scores[-1][1]
            drop = oldest_score - newest_score
            if drop >= BEHAVIOR_DROP_THRESHOLD:
                reasons.append(f"score_drop_{drop}")

        return {
            "is_distracted": len(reasons) > 0,
            "reasons": reasons,
            "idle_seconds": int(idle_seconds)
        }

    def get_idle_seconds(self) -> float:
        return getattr(self, "last_activity_elapsed", 0.0)
