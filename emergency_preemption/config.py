"""
config.py

Emergency Vehicle Preemption module configuration.
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
# FRAME
# ============================================================
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ============================================================
# VISUAL DETECTION - Emergency Light Colors (HSV ranges)
# ============================================================
# Red emergency lights (two HSV ranges for red wrap-around)
RED_LIGHT_LOW_1 = np.array([0, 120, 150])
RED_LIGHT_HIGH_1 = np.array([10, 255, 255])
RED_LIGHT_LOW_2 = np.array([165, 120, 150])
RED_LIGHT_HIGH_2 = np.array([180, 255, 255])

# Blue emergency lights
BLUE_LIGHT_LOW = np.array([100, 120, 150])
BLUE_LIGHT_HIGH = np.array([130, 255, 255])

# Amber/Orange lights (common in Indian emergency vehicles)
AMBER_LIGHT_LOW = np.array([10, 100, 200])
AMBER_LIGHT_HIGH = np.array([25, 255, 255])

# Minimum contour area for emergency light blobs
MIN_LIGHT_AREA = 100
MAX_LIGHT_AREA = 5000

# ============================================================
# BLINK DETECTION
# ============================================================
# Expected blink frequency range (Hz)
BLINK_FREQ_MIN = 1.0  # 1 Hz
BLINK_FREQ_MAX = 4.0  # 4 Hz
BLINK_HISTORY_FRAMES = 30  # Frames to analyze for blink pattern

# ============================================================
# SIREN DETECTION (Audio)
# ============================================================
# Indian siren frequency bands (Hz)
SIREN_FREQ_LOW = 600
SIREN_FREQ_HIGH = 1600
# Energy threshold for siren detection
SIREN_ENERGY_THRESHOLD = 0.05
# Audio sample rate
AUDIO_SAMPLE_RATE = 22050
AUDIO_CHUNK_SIZE = 2048

# ============================================================
# PREEMPTION LOGIC
# ============================================================
# Minimum confidence frames before state transition
MIN_ALERT_FRAMES = 5
MIN_YIELD_FRAMES = 10
# Vehicle size growth rate for approach detection
APPROACH_GROWTH_THRESHOLD = 0.05
