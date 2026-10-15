from transformers import pipeline
from PIL import Image
import torch
import io
from collections import deque
import cv2
import numpy as np

distraction_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# COCO objects that indicate the student is distracted
DISTRACTION_OBJECTS = {"cell phone", "remote", "book"}
DETECTION_THRESHOLD = 0.50
PHONE_VOTE_WINDOW = 3
PHONE_VOTES_REQUIRED = 2
_phone_votes = deque(maxlen=PHONE_VOTE_WINDOW)


def _green_phone_cue(image: Image.Image) -> bool:
    """Detect a compact, saturated green phone-like object as a demo fallback."""
    frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(frame, np.array([35, 75, 45]), np.array([90, 255, 245]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = frame.shape[0] * frame.shape[1]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.012 or area > frame_area * 0.30:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if width < 28 or height < 40:
            continue
        aspect = width / max(height, 1)
        if not 0.30 <= aspect <= 2.20:
            continue
        fill_ratio = area / max(width * height, 1)
        if fill_ratio >= 0.42:
            return True
    return False


def load_model():
    global distraction_pipeline
    print(f"[distraction_model] Using device: {DEVICE}")
    distraction_pipeline = pipeline(
        "object-detection",
        model="facebook/detr-resnet-50",
        device=DEVICE,
        framework="pt"
    )


def detect_distractions(image_bytes: bytes) -> dict:
    """
    Runs DETR object detection on a webcam frame.
    Returns phone_detected flag and list of distraction objects found.
    Threshold: 0.60 confidence to detect small phones in webcam frames.
    """
    if distraction_pipeline is None:
        return {"phone_detected": False, "distractions": []}

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = distraction_pipeline(image)

        detected = [
            r["label"].lower()
            for r in results
            if r["score"] >= DETECTION_THRESHOLD
        ]

        model_phone = "cell phone" in detected
        green_phone = _green_phone_cue(image)
        _phone_votes.append(model_phone or green_phone)
        phone_detected = (
            sum(_phone_votes) >= PHONE_VOTES_REQUIRED
            or any(
                r["label"].lower() == "cell phone" and r["score"] >= 0.72
                for r in results
            )
        )
        distractions_found = [d for d in detected if d in DISTRACTION_OBJECTS]
        if phone_detected and "cell phone" not in distractions_found:
            distractions_found.append("cell phone")

        return {
            "phone_detected": phone_detected,
            "distractions": distractions_found
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Distraction detection failed: {e}")
        return {
            "phone_detected": False,
            "distractions": []
        }
