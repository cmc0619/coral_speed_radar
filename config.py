"""Environment-based configuration. Export .env before running."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    camera_source: str = os.getenv("CAMERA_SOURCE", "0")
    frame_width: int = int(os.getenv("FRAME_WIDTH", "1280"))
    frame_height: int = int(os.getenv("FRAME_HEIGHT", "720"))
    model_path: str = os.getenv("MODEL_PATH", "models/detector.tflite")
    labels_path: str = os.getenv("LABELS_PATH", "models/coco_labels.txt")
    detection_confidence: float = float(os.getenv("DETECTION_CONFIDENCE", "0.55"))
    gate_a_x: int = int(os.getenv("GATE_A_X", "400"))
    gate_b_x: int = int(os.getenv("GATE_B_X", "900"))
    gate_distance_meters: float = float(os.getenv("GATE_DISTANCE_METERS", "6"))
    min_gate_seconds: float = float(os.getenv("MIN_GATE_SECONDS", "0.12"))
    max_gate_seconds: float = float(os.getenv("MAX_GATE_SECONDS", "4"))
    max_match_pixels: float = float(os.getenv("MAX_MATCH_PIXELS", "150"))
    track_timeout_seconds: float = float(os.getenv("TRACK_TIMEOUT_SECONDS", "0.8"))
    ocr_interval_seconds: float = float(os.getenv("OCR_INTERVAL_SECONDS", "0.2"))
    ocr_min_confidence: float = float(os.getenv("OCR_MIN_CONFIDENCE", "55"))
    ocr_min_votes: int = int(os.getenv("OCR_MIN_VOTES", "2"))
    database_path: str = os.getenv("DATABASE_PATH", "radar.db")
    post_mode: str = os.getenv("POST_MODE", "offline").lower()
    dashboard_host: str = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    def validate(self):
        if not (0 <= self.gate_a_x < self.gate_b_x < self.frame_width):
            raise ValueError("Invalid virtual gates or camera width")
        if self.frame_height < 1 or self.gate_distance_meters <= 0:
            raise ValueError("Invalid camera height or gate distance")
        if not (0 < self.min_gate_seconds < self.max_gate_seconds):
            raise ValueError("Invalid gate timing")
        if not 0 < self.detection_confidence <= 1:
            raise ValueError("Invalid detection threshold")
        if self.max_match_pixels <= 0 or self.track_timeout_seconds <= 0:
            raise ValueError("Invalid tracker thresholds")
        if self.ocr_min_votes < 1 or self.ocr_interval_seconds < 0:
            raise ValueError("Invalid OCR settings")
        if not 0 <= self.ocr_min_confidence <= 100:
            raise ValueError("Invalid OCR confidence")
        if self.post_mode not in ("offline", "x"):
            raise ValueError("POST_MODE must be offline or x")
        return self
