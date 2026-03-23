"""
config.py

Lane Assist + Blind Spot Detection configuration.
Imports shared constants and adds module-specific settings.
"""

import numpy as np
from shared import config_common as common

# ============================================================
# Re-export shared constants
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
DETECTION_INTERVAL = common.DETECTION_INTERVAL

# ============================================================
# FRAME (Rear Camera)
# ============================================================
BSD_WIDTH = 640
BSD_HEIGHT = 480

# ============================================================
# BLIND SPOT DETECTION - Bird's Eye View Transform
# ============================================================
BSD_ROI_SRC = np.float32([
    [174, 190],  # TL
    [80, 359],   # BL
    [496, 190],  # TR
    [610, 359]   # BR
])
BSD_ROI_DST = np.float32([
    [0, 0],
    [0, BSD_HEIGHT],
    [BSD_WIDTH, 0],
    [BSD_WIDTH, BSD_HEIGHT]
])

# ============================================================
# SLIDING WINDOW LANE DETECTION
# ============================================================
BSD_WINDOW_HEIGHT = 40
BSD_WINDOW_HALF_WIDTH = 50
BSD_MIN_PIXELS = 50
BSD_MAX_HISTORY = 10

# ============================================================
# DISTANCE CONVERSION (approximate for 640x480 standard lane)
# ============================================================
YM_PER_PIX = 30 / 480
XM_PER_PIX = 3.7 / 640

# ============================================================
# LANE CHANGE ADVISORY
# ============================================================
# Offset threshold to consider the vehicle drifting toward a lane
DRIFT_THRESHOLD_METERS = 0.3
# Minimum confidence frames before issuing advisory
MIN_ADVISORY_FRAMES = 3

# ============================================================
# BLIND SPOT SCAN REGION
# ============================================================
# Only scan lower portion of frame for blind spot vehicles.
# Vehicles above this line are too far away to be relevant.
BSD_SCAN_TOP_PCT = 0.20  # Ignore top 20%, scan bottom 80%
