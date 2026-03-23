"""
visual_detector.py

Visual detection of emergency vehicles using:
1. YOLOv8 to detect large vehicles (bus/truck)
2. HSV-based flashing light detection (red/blue/amber on top of vehicle)
3. Frame-to-frame blink frequency analysis
"""

import cv2
import numpy as np
from collections import deque
from emergency_preemption import config


class EmergencyLightDetector:
    """Detects flashing emergency lights on vehicles."""

    def __init__(self):
        # Track light presence per tracked vehicle over time
        # {track_id: deque of booleans (light_visible per frame)}
        self.light_history = {}

    def analyze(self, frame, tracked_objects):
        """
        Detect emergency lights on tracked vehicles.

        Args:
            frame: BGR frame
            tracked_objects: list of TrackState objects

        Returns:
            emergency_vehicles: list of dicts with vehicle info
                [{track_id, bbox, light_color, confidence, is_blinking}]
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        emergency_vehicles = []

        # Clean up old tracks
        current_ids = {obj.track_id for obj in tracked_objects}
        self.light_history = {
            k: v for k, v in self.light_history.items() if k in current_ids
        }

        for obj in tracked_objects:
            if len(obj.history) == 0:
                continue

            x1, y1, x2, y2 = map(int, obj.history[-1])
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)

            # Focus on top 30% of bounding box (where lights are)
            light_region_h = max(1, int((y2 - y1) * 0.3))
            roi = hsv[y1:y1 + light_region_h, x1:x2]

            if roi.size == 0:
                continue

            # Detect colored lights
            light_color, light_mask = self._detect_light_color(roi)

            light_visible = False
            if light_color and light_mask is not None:
                light_area = cv2.countNonZero(light_mask)
                if config.MIN_LIGHT_AREA <= light_area <= config.MAX_LIGHT_AREA:
                    light_visible = True

            # Track history for blink detection
            if obj.track_id not in self.light_history:
                self.light_history[obj.track_id] = deque(
                    maxlen=config.BLINK_HISTORY_FRAMES)

            self.light_history[obj.track_id].append(light_visible)

            # Check for blinking pattern
            is_blinking = self._detect_blink(obj.track_id)

            # Check if YOLO model explicitly recognized it as an emergency class
            ev_classes = ['ambulance', 'ambulance_108', 'ambulance_SOL', 'fire_truck', 'police']
            yolo_is_ev = any(c in obj.class_name for c in ev_classes)

            # High confidence if YOLO model explicitly labels it an emergency vehicle
            # Or if it detects blinking emergency lights
            if is_blinking or light_visible or yolo_is_ev:
                confidence = 0.5
                if yolo_is_ev and is_blinking:
                    confidence = 0.95
                elif yolo_is_ev:
                    confidence = 0.8
                elif is_blinking:
                    confidence = 0.9

                emergency_vehicles.append({
                    'track_id': obj.track_id,
                    'bbox': (x1, y1, x2, y2),
                    'light_color': light_color or 'unknown',
                    'confidence': confidence,
                    'is_blinking': is_blinking,
                    'class_name': obj.class_name
                })

        return emergency_vehicles

    def _detect_light_color(self, hsv_roi):
        """
        Detect emergency light color in ROI.
        Returns (color_name, mask) or (None, None).
        """
        # Red lights (two ranges)
        red_mask1 = cv2.inRange(hsv_roi, config.RED_LIGHT_LOW_1,
                                config.RED_LIGHT_HIGH_1)
        red_mask2 = cv2.inRange(hsv_roi, config.RED_LIGHT_LOW_2,
                                config.RED_LIGHT_HIGH_2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        # Blue lights
        blue_mask = cv2.inRange(hsv_roi, config.BLUE_LIGHT_LOW,
                                config.BLUE_LIGHT_HIGH)

        # Amber lights
        amber_mask = cv2.inRange(hsv_roi, config.AMBER_LIGHT_LOW,
                                 config.AMBER_LIGHT_HIGH)

        # Return the most prominent
        red_count = cv2.countNonZero(red_mask)
        blue_count = cv2.countNonZero(blue_mask)
        amber_count = cv2.countNonZero(amber_mask)

        max_count = max(red_count, blue_count, amber_count)

        if max_count < config.MIN_LIGHT_AREA:
            return None, None

        if red_count == max_count:
            return 'red', red_mask
        elif blue_count == max_count:
            return 'blue', blue_mask
        else:
            return 'amber', amber_mask

    def _detect_blink(self, track_id):
        """
        Detect blinking pattern from light visibility history.
        Returns True if a blinking pattern is detected.
        """
        history = self.light_history.get(track_id)
        if history is None or len(history) < 10:
            return False

        # Count transitions (on->off or off->on)
        transitions = 0
        hist_list = list(history)
        for i in range(1, len(hist_list)):
            if hist_list[i] != hist_list[i - 1]:
                transitions += 1

        # Estimate blink frequency
        # transitions / 2 = cycles in N frames
        # At ~30 FPS, N frames = N/30 seconds
        fps_estimate = 30.0
        duration_sec = len(hist_list) / fps_estimate
        if duration_sec <= 0:
            return False

        cycles = transitions / 2.0
        freq = cycles / duration_sec

        return config.BLINK_FREQ_MIN <= freq <= config.BLINK_FREQ_MAX
