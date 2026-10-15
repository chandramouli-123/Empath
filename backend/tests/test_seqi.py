import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.seqi import SEQIEngine, EMOTION_ENGAGEMENT_WEIGHT


def test_emotion_engagement_weights():
    """Verify exact multiplier constants as requested."""
    assert EMOTION_ENGAGEMENT_WEIGHT["focused"] == 1.0
    assert EMOTION_ENGAGEMENT_WEIGHT["neutral"] == 0.85
    assert EMOTION_ENGAGEMENT_WEIGHT["confused"] == 0.58
    assert EMOTION_ENGAGEMENT_WEIGHT["bored"] == 0.40
    assert EMOTION_ENGAGEMENT_WEIGHT["distressed"] == 0.25
    assert EMOTION_ENGAGEMENT_WEIGHT["distracted"] == 0.15


def test_focused_score_range():
    """Focused should settle within 80-95."""
    engine = SEQIEngine()
    result = None
    for sec in range(1, 30):
        result = engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    assert 80 <= result["seqi_score"] <= 95
    assert result["engagement_state"] == "focused"


def test_neutral_score_range():
    """Neutral should settle within 70-80."""
    engine = SEQIEngine()
    result = None
    for sec in range(1, 30):
        result = engine.update("neutral", [], elapsed_seconds=sec, is_distracted=False)
    assert 70 <= result["seqi_score"] <= 80


def test_confused_score_drop():
    """Confused should cause score to drop into 45-55."""
    engine = SEQIEngine()
    # Start focused
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    # Transition to confused
    result = None
    for sec in range(15, 50):
        result = engine.update("confused", [], elapsed_seconds=sec, is_distracted=False)
    assert 45 <= result["seqi_score"] <= 55
    assert result["engagement_state"] in ("confused", "neutral")


def test_bored_score_drop():
    """Bored should cause score to drop into 30-42."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    result = None
    for sec in range(15, 50):
        result = engine.update("bored", [], elapsed_seconds=sec, is_distracted=False)
    assert 30 <= result["seqi_score"] <= 42


def test_distressed_score_drop():
    """Distressed should cause score to drop below 30."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    result = None
    for sec in range(15, 50):
        result = engine.update("distressed", [], elapsed_seconds=sec, is_distracted=False)
    assert result["seqi_score"] < 30


def test_distracted_score_drop():
    """Distracted (behavioral or emotion) should drop into 15-25 or lower."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    result = None
    for sec in range(15, 50):
        result = engine.update("distracted", [], elapsed_seconds=sec, is_distracted=True)
    assert result["seqi_score"] <= 25
    assert result["engagement_state"] == "distracted"


def test_ema_smoothing_prevents_erratic_jumps():
    """A single isolated bored frame should not immediately crater the score."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, is_distracted=False)
    high_score = engine._smoothed_seqi
    
    # 1 single bored frame
    single_frame = engine.update("bored", [], elapsed_seconds=16, is_distracted=False)
    
    # Score should drop smoothly, not jump all the way down in one frame
    drop = high_score - single_frame["seqi_score"]
    assert drop <= 10, f"Expected smooth drop <= 10, but dropped {drop}"


def test_low_confidence_negative_emotion_is_attenuated():
    """Uncertain facial predictions should not crater the real-time score."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, confidence=0.95)
    high_score = engine._smoothed_seqi

    result = engine.update(
        "bored", [], elapsed_seconds=16, confidence=0.35
    )

    assert high_score - result["seqi_score"] <= 6


def test_high_confidence_negative_emotion_retains_penalty():
    """High-conviction negative emotion should still affect SEQI strongly."""
    engine = SEQIEngine()
    for sec in range(1, 15):
        engine.update("focused", [], elapsed_seconds=sec, confidence=0.95)
    high_score = engine._smoothed_seqi

    result = engine.update(
        "bored", [], elapsed_seconds=16, confidence=0.90
    )

    assert high_score - result["seqi_score"] >= 4
