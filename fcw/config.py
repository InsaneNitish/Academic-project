"""
config.py

FCW-specific configuration.
Imports shared constants and adds module-specific thresholds.
"""

import numpy as np
from shared import config_common as common

# ============================================================
# Re-export shared constants for convenience
# ============================================================
CAMERA_INDEX = common.CAMERA_INDEX
USE_GPU = common.USE_GPU
MODEL_PATH = common.MODEL_PATH
CONFIDENCE_THRESHOLD = common.CONFIDENCE_THRESHOLD
TARGET_CLASSES = common.TARGET_CLASSES
CLASS_NAMES = common.CLASS_NAMES
TRACK_HISTORY_LEN = common.TRACK_HISTORY_LEN
MIN_HITS = common.MIN_HITS
MAX_AGE = common.MAX_AGE
DETECTION_INTERVAL = 3   # Run YOLO every 3rd frame (was 2) for speed
SMOOTHING_ALPHA = common.SMOOTHING_ALPHA
SMOOTHING_WINDOW = common.SMOOTHING_WINDOW

# ============================================================
# FRAME
# ============================================================
FRAME_WIDTH = 640
FRAME_HEIGHT = 360

# ============================================================
# EGO PATH — defines the forward driving corridor
# ============================================================
EGO_WIDTH_PCT = 0.45       # Center 45% of frame width (slightly wider)
EGO_HEIGHT_PCT = 0.65      # Bottom 65% of frame height
EGO_OVERLAP_THRESH = 0.25  # 25% horizontal overlap = in-path

# ============================================================
# DISTANCE ESTIMATION — class-specific real-world heights (meters)
# Pinhole model: distance = (real_height * focal_length) / pixel_height
# ============================================================
FOCAL_LENGTH_PX = 500      # Approximate focal length for 640px dashcam

REAL_HEIGHTS = {
    0: 1.70,   # pedestrian
    2: 1.50,   # car
    3: 1.10,   # motorcycle
    5: 3.20,   # bus
    7: 3.50,   # truck
}
DEFAULT_REAL_HEIGHT = 1.50  # Fallback

# ============================================================
# TTC (Time-to-Collision) ESTIMATION
# ============================================================
TTC_HISTORY_LEN = 8         # Distance samples for regression
MIN_CLOSING_SPEED = 0.3     # m/s — ignore slower approach rates (noise)
TTC_MAX_DISPLAY = 30.0      # Don't display TTC above this

# ============================================================
# MOTION METRICS
# ============================================================
THRESH_GROWTH = 0.18
THRESH_VERTICAL = 4.0
MIN_TRACK_AGE_SEC = 0.5
COOLDOWN_SECONDS = 1.0
SUDDEN_ENTRY_GROWTH_PERSISTENCE = 0.3

# ============================================================
# TRAFFIC CONTEXT THRESHOLDS
# ============================================================
TRAFFIC_MODERATE_THRESHOLD = 4   # >= 4 vehicles = moderate traffic
TRAFFIC_HEAVY_THRESHOLD = 8     # >= 8 vehicles = heavy traffic

# ============================================================
# FCW / COLLISION
# ============================================================
FCW_TTC_CRITICAL = 2.0
FCW_TTC_WARNING = 4.0
FCW_SCALE_FACTOR = 1000
MAX_WARNING_DISTANCE = 50.0  # Only warn if vehicle is within 50 meters

# ============================================================
# VERIFICATION
# ============================================================
FPS_TARGET = 15

