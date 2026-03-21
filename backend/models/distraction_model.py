from transformers import pipeline
from PIL import Image
import torch
import io

distraction_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# COCO objects that indicate the student is distracted
DISTRACTION_OBJECTS = {"cell phone", "remote", "book"}


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
    Threshold: 0.75 confidence to reduce false positives.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = distraction_pipeline(image)

        detected = [
            r["label"].lower()
            for r in results
            if r["score"] > 0.75
        ]

        phone_detected = "cell phone" in detected
        distractions_found = [d for d in detected if d in DISTRACTION_OBJECTS]

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
