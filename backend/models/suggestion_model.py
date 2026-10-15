"""
Suggestion Model — Rule-based gating + structured FLAN-T5 generation.

Suggestions depend ONLY on:
  - Last 60s behavioral metrics
  - Current emotion class
  - Current SEQI trend slope
  - Video timestamp

Rule-based gating filters decide WHAT to suggest.
FLAN-T5 generates the natural language text.
"""
from transformers import pipeline
import torch
import logging

logger = logging.getLogger(__name__)

suggestion_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Maps engagement state → action code for the frontend
ACTION_MAP = {
    "confused": "slow_video",
    "bored": "speed_up",
    "distressed": "show_break",
    "distracted": "show_break",
    "focused": "none"
}

# Fallback suggestions when model fails
FALLBACK_SUGGESTIONS = {
    "confused": "Try rewinding to the last concept and watching at a slower speed.",
    "bored": "Skip ahead to the next section for fresh material!",
    "distressed": "Take a 2-minute break — stretch and breathe. You'll come back stronger.",
    "distracted": "Time for a quick check-in — are you still with the video?",
    "focused": "Great focus! Keep it up."
}


def load_model():
    global suggestion_pipeline
    print(f"[suggestion_model] Using device: {DEVICE}")
    suggestion_pipeline = pipeline(
        "text2text-generation",
        model="google/flan-t5-base",
        max_new_tokens=60,
        device=DEVICE,
        framework="pt"
    )


def _apply_gating_rules(emotion: str, behavioral_summary: dict,
                        seqi_trend: float) -> dict:
    """
    Rule-based gating: determine suggestion category and action
    BEFORE calling FLAN-T5.

    Returns { category, action, context_hint }
    """
    rewinds = behavioral_summary.get("rewinds", 0)
    fast_forwards = behavioral_summary.get("fast_forwards", 0)
    pauses = behavioral_summary.get("pauses", 0)
    idles = behavioral_summary.get("idles", 0)
    tab_switches = behavioral_summary.get("tab_switches", 0)

    # Rule 1: Confused + frequent rewinds → suggest explanation/summary
    if emotion == "confused" and rewinds >= 2:
        return {
            "category": "explain",
            "action": "slow_video",
            "context_hint": "struggling with a concept, has rewound multiple times"
        }

    # Rule 2: Confused + no rewinds → suggest slowing down
    if emotion == "confused":
        return {
            "category": "slow_down",
            "action": "slow_video",
            "context_hint": "looks confused but hasn't tried rewinding yet"
        }

    # Rule 3: Bored + fast forwarding → suggest speed increase or quiz
    if emotion == "bored" and fast_forwards >= 1:
        return {
            "category": "engage",
            "action": "speed_up",
            "context_hint": "bored and skipping content, needs a challenge"
        }

    # Rule 4: Bored + no action → suggest skipping ahead
    if emotion == "bored":
        return {
            "category": "skip",
            "action": "speed_up",
            "context_hint": "losing interest, needs something new"
        }

    # Rule 5: Distracted + idle → suggest break/check-in
    if emotion == "distracted" and (idles >= 1 or tab_switches >= 1):
        return {
            "category": "check_in",
            "action": "show_break",
            "context_hint": "distracted — left the tab or been idle"
        }

    # Rule 6: Distracted (other) → gentle nudge
    if emotion == "distracted":
        return {
            "category": "nudge",
            "action": "show_break",
            "context_hint": "showing signs of distraction"
        }

    # Rule 7: Distressed + score dropping → suggest pause and breathing
    if emotion == "distressed" and seqi_trend < -5:
        return {
            "category": "break",
            "action": "show_break",
            "context_hint": "stressed and engagement is rapidly declining"
        }

    # Rule 8: Distressed (stable) → encourage
    if emotion == "distressed":
        return {
            "category": "support",
            "action": "show_break",
            "context_hint": "feeling stressed but engagement is stable"
        }

    # Rule 9: Focused but trending down → light nudge
    if emotion == "focused" and seqi_trend < -3:
        return {
            "category": "prevent",
            "action": "nudge",
            "context_hint": "currently focused but engagement starting to decline"
        }

    # Default: no suggestion needed
    return {
        "category": "none",
        "action": "none",
        "context_hint": "engaged and on track"
    }


def generate_suggestion(emotion: str, topic: str,
                        behavioral_summary: dict = None,
                        seqi_trend: float = 0.0,
                        video_timestamp: float = 0.0) -> dict:
    """
    Generate a suggestion using rule-based gating + structured FLAN-T5 context.
    """
    if behavioral_summary is None:
        behavioral_summary = {}

    # Step 1: Apply gating rules
    gate = _apply_gating_rules(emotion, behavioral_summary, seqi_trend)

    if gate["category"] == "none":
        return {"suggestion": "", "action": "none"}

    action = gate["action"]

    # Step 2: Build structured context for FLAN-T5
    ts_str = f"{int(video_timestamp // 60)}:{int(video_timestamp % 60):02d}"

    if suggestion_pipeline is None:
        return {
            "suggestion": FALLBACK_SUGGESTIONS.get(emotion, "Take a moment to refocus."),
            "action": action,
            "category": gate["category"]
        }

    try:
        prompt = (
            f"You are a learning assistant. Generate one short, specific suggestion.\n"
            f"Emotion: {emotion}\n"
            f"Context: Student is {gate['context_hint']}\n"
            f"Topic: {topic}\n"
            f"Video time: {ts_str}\n"
            f"Rewinds: {behavioral_summary.get('rewinds', 0)} | "
            f"Pauses: {behavioral_summary.get('pauses', 0)} | "
            f"Fast-forwards: {behavioral_summary.get('fast_forwards', 0)}\n"
            f"SEQI trend: {'declining' if seqi_trend < -2 else 'stable' if abs(seqi_trend) <= 2 else 'improving'}\n"
            f"Write one actionable sentence (max 15 words). No generic motivation."
        )

        result = suggestion_pipeline(prompt)[0]["generated_text"].strip()

        # Guard against empty or too short output
        if not result or len(result) < 5:
            result = FALLBACK_SUGGESTIONS.get(emotion, "Take a moment to refocus.")

    except Exception as e:
        logger.warning(f"Suggestion pipeline fallback used: {e}")
        result = FALLBACK_SUGGESTIONS.get(emotion, "Take a moment to refocus.")

    return {
        "suggestion": result,
        "action": action,
        "category": gate["category"]
    }
