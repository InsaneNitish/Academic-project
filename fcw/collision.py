"""
collision.py

Context-Aware Forward Collision Warning (FCW) Engine.
Uses ego-path geometry for in-path filtering (no lane detection).
Class-specific distance estimation and regression-based TTC.
"""

import numpy as np
from fcw import config
from fcw.ego_path import is_in_ego_path, get_ego_region
from collections import deque


def estimate_distance(bbox_height, class_id=2):
    """
    Estimate distance using pinhole camera model with class-specific heights.
    distance = (real_height * focal_length) / pixel_height
    """
    if bbox_height < 1:
        return 999.0
    real_h = config.REAL_HEIGHTS.get(class_id, config.DEFAULT_REAL_HEIGHT)
    return (real_h * config.FOCAL_LENGTH_PX) / bbox_height


def _compute_ttc_regression(distances, fps):
    """
    Compute TTC using weighted linear regression over distance history.
    More recent samples get higher weight — reduces bbox jitter noise.

    Returns: (ttc_seconds, closing_speed_mps)
    """
    n = len(distances)
    if n < 3:
        return 99.0, 0.0

    # Time axis in seconds (most recent = 0, oldest = negative)
    dt = 1.0 / max(fps, 1.0)
    t = np.array([-(n - 1 - i) * dt for i in range(n)])
    d = np.array(distances)

    # Exponential weights — newest samples weighted most
    weights = np.array([1.5 ** i for i in range(n)])

    # Weighted least squares: d = slope * t + intercept
    w_sum = weights.sum()
    t_mean = np.dot(weights, t) / w_sum
    d_mean = np.dot(weights, d) / w_sum

    t_centered = t - t_mean
    d_centered = d - d_mean

    numerator = np.dot(weights, t_centered * d_centered)
    denominator = np.dot(weights, t_centered ** 2)

    if abs(denominator) < 1e-9:
        return 99.0, 0.0

    slope = numerator / denominator  # m/s (negative = approaching)

    # Closing speed is negative slope (distance decreasing over time)
    closing_speed = -slope

    if closing_speed < config.MIN_CLOSING_SPEED:
        return 99.0, closing_speed

    # Current distance (most recent sample)
    current_dist = d[-1]
    ttc = current_dist / closing_speed

    return max(0.0, min(ttc, 99.0)), closing_speed


class FCWEngine:
    def __init__(self):
        self.track_data = {}  # {track_id: deque of distances}

    def analyze(self, tracks, frame_w, frame_h, fps, vehicle_count=0):
        """
        Analyze tracks for collision risk using ego-path filtering.

        Args:
            tracks: list of TrackState objects
            frame_w, frame_h: frame dimensions
            fps: video FPS
            vehicle_count: total detected vehicles (for traffic context)

        Returns:
            fcw_state (str): "SAFE", "WARNING", "DANGER"
            target_id (int): ID of the critical vehicle
            ttc (float): Estimated Time-to-Collision
            distances (dict): {track_id: (distance_m, ttc, closing_speed)} for in-path vehicles
        """
        distances = {}

        if not tracks:
            return "SAFE", None, None, distances

        # ── Traffic Context ──────────────────────────────────────
        is_heavy = vehicle_count >= config.TRAFFIC_HEAVY_THRESHOLD
        is_moderate = vehicle_count >= config.TRAFFIC_MODERATE_THRESHOLD

        if is_heavy:
            ttc_critical = config.FCW_TTC_CRITICAL * 0.5
            ttc_warning = config.FCW_TTC_WARNING * 0.5
        elif is_moderate:
            ttc_critical = config.FCW_TTC_CRITICAL * 0.7
            ttc_warning = config.FCW_TTC_WARNING * 0.7
        else:
            ttc_critical = config.FCW_TTC_CRITICAL
            ttc_warning = config.FCW_TTC_WARNING

        # ── Filter In-Path Vehicles ──────────────────────────────
        current_ids = set()
        candidates = []

        for obj in tracks:
            current_ids.add(obj.track_id)

            if len(obj.history) == 0:
                continue

            x1, y1, x2, y2 = obj.history[-1]
            bbox = (x1, y1, x2, y2)

            if not is_in_ego_path(bbox, frame_w, frame_h):
                continue

            # Class-specific distance
            bbox_h = max(1, y2 - y1)
            class_id = getattr(obj, 'class_id', 2)
            dist_m = estimate_distance(bbox_h, class_id)

            # Skip unreasonably far vehicles
            if dist_m > config.MAX_WARNING_DISTANCE:
                continue

            # Update distance history
            if obj.track_id not in self.track_data:
                self.track_data[obj.track_id] = deque(
                    maxlen=config.TTC_HISTORY_LEN)

            self.track_data[obj.track_id].append(dist_m)

            # Compute TTC via regression
            ttc_val, closing_speed = _compute_ttc_regression(
                list(self.track_data[obj.track_id]), fps)

            distances[obj.track_id] = (dist_m, ttc_val, closing_speed)
            candidates.append((obj, dist_m, ttc_val))

        # Cleanup stale tracks
        stale = [k for k in self.track_data if k not in current_ids]
        for k in stale:
            del self.track_data[k]

        if not candidates:
            return "SAFE", None, None, distances

        # ── Find Most Critical Target ────────────────────────────
        # Sort by TTC ascending (most urgent first), then distance
        candidates.sort(key=lambda c: (c[2], c[1]))
        target_obj, target_dist, target_ttc = candidates[0]
        tid = target_obj.track_id

        # ── Decision ─────────────────────────────────────────────
        state = "SAFE"

        if target_dist < config.MAX_WARNING_DISTANCE:
            if target_ttc < ttc_critical:
                state = "DANGER"
            elif target_ttc < ttc_warning:
                state = "WARNING"

        return state, tid, target_ttc, distances
