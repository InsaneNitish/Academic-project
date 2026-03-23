"""
traffic_engine.py

Core engine for extracting traffic features and classifying context.
"""

import cv2
import numpy as np
from collections import deque
from fcw import config
from typing import List, Dict, Any


class TrafficEngine:
    def __init__(self):
        self.density_history = deque(maxlen=config.SMOOTHING_WINDOW)
        self.speed_history = deque(maxlen=config.SMOOTHING_WINDOW)

    def extract_features(self, inlane_objects: List[Any],
                         drivable_mask: np.ndarray,
                         fps: float) -> Dict[str, Any]:
        """Computes traffic features from relevant objects and road mask."""
        vehicle_count_current = len(inlane_objects)

        if drivable_mask is not None:
            road_area_pixels = cv2.countNonZero(drivable_mask)
        else:
            road_area_pixels = 1

        density_value = vehicle_count_current / road_area_pixels if road_area_pixels > 0 else 0

        speeds = []
        total_bbox_area = 0

        for obj in inlane_objects:
            s = getattr(obj, 'speed_estimate', 0)
            speeds.append(s)

            if hasattr(obj, 'history') and len(obj.history) > 0:
                x1, y1, x2, y2 = obj.history[-1]
                total_bbox_area += (x2 - x1) * (y2 - y1)

        avg_speed_px = np.mean(speeds) if speeds else 0
        speed_variance_value = np.var(speeds) if speeds else 0

        lane_occupancy_ratio = total_bbox_area / road_area_pixels if road_area_pixels > 0 else 0

        self.density_history.append(density_value)
        self.speed_history.append(avg_speed_px)

        density_smoothed = np.mean(self.density_history)
        speed_smoothed = np.mean(self.speed_history)

        return {
            "vehicle_count_current": vehicle_count_current,
            "road_area_pixels": road_area_pixels,
            "density_value": density_value,
            "avg_speed_px": avg_speed_px,
            "speed_variance_value": speed_variance_value,
            "lane_occupancy_ratio": lane_occupancy_ratio,
            "density_smoothed": density_smoothed,
            "speed_smoothed": speed_smoothed
        }

    def classify_context(self, features: Dict[str, Any]) -> str:
        """Rule-based Traffic Context Classifier."""
        s = features["speed_smoothed"]
        occ = features["lane_occupancy_ratio"]

        if occ > config.THRESH_OCCUPANCY_HIGH and s < config.THRESH_SPEED_LOW:
            return "CONGESTION"
        elif occ > config.THRESH_OCCUPANCY_MED:
            return "MODERATE_TRAFFIC"
        else:
            return "FREE_FLOW"
