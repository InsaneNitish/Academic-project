"""
preemption_logic.py

Fuses visual (emergency light) and audio (siren) signals to determine
whether the ego vehicle should yield to an emergency vehicle.

States:
    NORMAL  - No emergency vehicle detected
    ALERT   - Possible emergency vehicle (low confidence)
    YIELD   - Confirmed emergency vehicle, driver should yield
"""

import numpy as np
from collections import deque
from emergency_preemption import config


class PreemptionEngine:
    """Fuses auditory + visual signals for emergency vehicle detection."""

    NORMAL = "NORMAL"
    ALERT = "ALERT"
    YIELD = "YIELD"

    def __init__(self):
        self.state = self.NORMAL
        self.alert_frames = 0
        self.yield_frames = 0
        self.decay_frames = 0

        # Track approaching direction
        self.approach_direction = None
        self.vehicle_growth_history = {}

    def analyze(self, visual_detections, siren_detected, siren_confidence,
                tracked_objects=None):
        """
        Determine preemption state from fused signals.

        Args:
            visual_detections: list of dicts from EmergencyLightDetector
            siren_detected: bool from SirenDetector
            siren_confidence: float from SirenDetector
            tracked_objects: optional list of all tracked objects for direction

        Returns:
            state (str): "NORMAL", "ALERT", or "YIELD"
            details (dict): Decision details
        """
        # Score computation
        visual_score = 0.0
        audio_score = 0.0

        # Visual scoring
        if visual_detections:
            best_visual = max(visual_detections, key=lambda d: d['confidence'])
            visual_score = best_visual['confidence']

            # Detect approach direction
            if tracked_objects:
                self._update_approach_direction(best_visual, tracked_objects)

        # Audio scoring
        if siren_detected:
            audio_score = siren_confidence

        # Fused confidence
        # Multi-modal fusion: higher weight to confirmed blinking lights
        fused_score = max(visual_score, audio_score)
        if visual_score > 0.3 and audio_score > 0.3:
            # Both modalities agree: boost confidence
            fused_score = min(1.0, visual_score * 0.6 + audio_score * 0.4 + 0.2)

        # State machine
        if fused_score >= 0.7:
            self.yield_frames += 1
            self.alert_frames += 1
            self.decay_frames = 0
        elif fused_score >= 0.3:
            self.alert_frames += 1
            self.decay_frames = 0
        else:
            self.decay_frames += 1
            if self.decay_frames > 15:
                self.alert_frames = max(0, self.alert_frames - 1)
                self.yield_frames = max(0, self.yield_frames - 1)

        # State transitions
        new_state = self.NORMAL

        if self.yield_frames >= config.MIN_YIELD_FRAMES:
            new_state = self.YIELD
        elif self.alert_frames >= config.MIN_ALERT_FRAMES:
            new_state = self.ALERT

        # Don't jump from NORMAL directly to YIELD
        if self.state == self.NORMAL and new_state == self.YIELD:
            new_state = self.ALERT

        self.state = new_state

        # Build details
        details = {
            "fused_score": round(fused_score, 2),
            "visual_score": round(visual_score, 2),
            "audio_score": round(audio_score, 2),
            "alert_frames": self.alert_frames,
            "yield_frames": self.yield_frames,
            "approach_direction": self.approach_direction,
            "num_emergency_vehicles": len(visual_detections) if visual_detections else 0,
        }

        return self.state, details

    def _update_approach_direction(self, detection, tracked_objects):
        """Estimate approach direction of the emergency vehicle."""
        tid = detection['track_id']
        bbox = detection['bbox']
        x1, y1, x2, y2 = bbox

        cx = (x1 + x2) / 2
        frame_center_x = config.FRAME_WIDTH / 2

        # Track growth (approaching = getting bigger)
        bbox_area = (x2 - x1) * (y2 - y1)
        if tid not in self.vehicle_growth_history:
            self.vehicle_growth_history[tid] = deque(maxlen=10)
        self.vehicle_growth_history[tid].append(bbox_area)

        # Direction based on position
        if cx < frame_center_x * 0.6:
            self.approach_direction = "LEFT"
        elif cx > frame_center_x * 1.4:
            self.approach_direction = "RIGHT"
        else:
            self.approach_direction = "BEHIND"

    def reset(self):
        """Reset state machine."""
        self.state = self.NORMAL
        self.alert_frames = 0
        self.yield_frames = 0
        self.decay_frames = 0
        self.approach_direction = None
