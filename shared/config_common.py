"""
config_common.py

Shared configuration constants used across all ADAS modules.
Module-specific configs import from here and add their own settings.
"""

import numpy as np

# ============================================================
# SYSTEM
# ============================================================
CAMERA_INDEX = 0
USE_GPU = True

# ============================================================
# YOLOv8 Model
# ============================================================
MODEL_PATH = "yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.4

# COCO class mapping (relevant vehicle/person classes)
TARGET_CLASSES = [0, 2, 3, 5, 7]
CLASS_NAMES = {
    0: "pedestrian",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# ============================================================
# TRACKING (DeepSORT)
# ============================================================
TRACK_HISTORY_LEN = 10
MIN_HITS = 3
MAX_AGE = 10
DETECTION_INTERVAL = 1 # Run YOLO every Nth frame (tracker predicts in between)

# ============================================================
# UI COLORS (BGR format for OpenCV)
# ============================================================
COLOR_SAFE = (118, 230, 0)       # #00E676 Green
COLOR_WARNING = (0, 179, 255)    # #FFB300 Amber
COLOR_DANGER = (68, 23, 255)     # #FF1744 Red
COLOR_INFO = (246, 182, 41)      # #29B6F6 Light Blue
COLOR_BG_DARK = (20, 20, 20)     # Dark panel background
COLOR_WHITE = (255, 255, 255)
COLOR_TEXT_DIM = (160, 160, 160)

# ============================================================
# SMOOTHING
# ============================================================
SMOOTHING_ALPHA = 0.3
SMOOTHING_WINDOW = 5
