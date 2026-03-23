"""
lane_change_advisor.py

Combines Blind Spot Detection output with lane offset to determine
whether a lane change is safe.

Advisory States:
    SAFE_LEFT    - Left lane change is safe
    SAFE_RIGHT   - Right lane change is safe
    SAFE_BOTH    - Both directions are safe
    UNSAFE_LEFT  - Left blind spot occupied
    UNSAFE_RIGHT - Right blind spot occupied
    UNSAFE_BOTH  - Both blind spots occupied
    NO_DATA      - Insufficient lane data
"""

import cv2
from lane_assist import config


class LaneChangeAdvisor:
    """Decision engine that fuses blind spot status + lane position."""

    def __init__(self):
        self.left_unsafe_frames = 0
        self.right_unsafe_frames = 0

    def analyze(self, tracked_objects, cubes, lane_info):
        """
        Determine lane change safety.

        Args:
            tracked_objects: list of TrackState from tracker
            cubes: list of [left_cube_poly, right_cube_poly] from BSD
            lane_info: dict with 'offset', 'direction', etc. (or None)

        Returns:
            advisory (str): One of the advisory states
            details (dict): Detailed breakdown of the decision
        """
        if not cubes or lane_info is None:
            self.left_unsafe_frames = 0
            self.right_unsafe_frames = 0
            return "NO_DATA", {"reason": "Insufficient lane/blind spot data"}

        # Check blind spot occupancy
        left_occupied = False
        right_occupied = False

        for obj in tracked_objects:
            if len(obj.history) > 0:
                x1, y1, x2, y2 = obj.history[-1]
                point = ((x1 + x2) / 2, y2)

                if len(cubes) >= 1 and cubes[0] is not None:
                    if cv2.pointPolygonTest(cubes[0], point, False) >= 0:
                        left_occupied = True
                if len(cubes) >= 2 and cubes[1] is not None:
                    if cv2.pointPolygonTest(cubes[1], point, False) >= 0:
                        right_occupied = True

        # Track persistence
        if left_occupied:
            self.left_unsafe_frames += 1
        else:
            self.left_unsafe_frames = max(0, self.left_unsafe_frames - 1)

        if right_occupied:
            self.right_unsafe_frames += 1
        else:
            self.right_unsafe_frames = max(0, self.right_unsafe_frames - 1)

        left_confirmed = self.left_unsafe_frames >= config.MIN_ADVISORY_FRAMES
        right_confirmed = self.right_unsafe_frames >= config.MIN_ADVISORY_FRAMES

        # Lane offset context
        offset = lane_info.get('offset', 0)
        drifting_left = offset < -config.DRIFT_THRESHOLD_METERS
        drifting_right = offset > config.DRIFT_THRESHOLD_METERS

        # Determine advisory
        details = {
            "left_occupied": left_occupied,
            "right_occupied": right_occupied,
            "left_confirmed": left_confirmed,
            "right_confirmed": right_confirmed,
            "offset": offset,
            "drifting_left": drifting_left,
            "drifting_right": drifting_right,
        }

        # Critical warning: drifting toward occupied blind spot
        if drifting_left and left_confirmed:
            details["warning"] = "DON'T MOVE LEFT!"
            return "UNSAFE_LEFT", details
        if drifting_right and right_confirmed:
            details["warning"] = "DON'T MOVE RIGHT!"
            return "UNSAFE_RIGHT", details

        # General advisory
        if left_confirmed and right_confirmed:
            details["warning"] = "STAY IN LANE"
            return "UNSAFE_BOTH", details
        elif left_confirmed:
            return "UNSAFE_LEFT", details
        elif right_confirmed:
            return "UNSAFE_RIGHT", details
        elif not left_occupied and not right_occupied:
            return "SAFE_BOTH", details
        elif not left_occupied:
            return "SAFE_LEFT", details
        elif not right_occupied:
            return "SAFE_RIGHT", details
        else:
            return "SAFE_BOTH", details
