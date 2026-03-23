"""
tracker.py

Manages track history and state using DeepSORT.
Shared across all ADAS modules.
"""

from typing import Dict, List, Any, Deque
from collections import deque
import time
from shared import config_common as cfg
from deep_sort_realtime.deepsort_tracker import DeepSort


class TrackState:
    """Represents the state of a single tracked object."""

    def __init__(self, track_id: int):
        self.track_id = track_id
        self.history: Deque[Any] = deque(maxlen=cfg.TRACK_HISTORY_LEN)
        self.last_update_time = time.time()
        self.age = 0
        self.missed_frames = 0
        self.class_id = -1
        self.class_name = ""
        self.speed_estimate = 0.0  # pixels/frame
        self.features = None

    def update(self, bbox, class_id, class_name):
        self.history.append(bbox)
        self.last_update_time = time.time()
        self.age += 1
        self.missed_frames = 0
        self.class_id = class_id
        self.class_name = class_name

        # Calculate speed (centroid delta)
        if len(self.history) >= 2:
            prev_box = self.history[-2]
            curr_box = self.history[-1]

            cx_prev = (prev_box[0] + prev_box[2]) / 2
            cy_prev = (prev_box[1] + prev_box[3]) / 2
            cx_curr = (curr_box[0] + curr_box[2]) / 2
            cy_curr = (curr_box[1] + curr_box[3]) / 2

            dist = ((cx_curr - cx_prev) ** 2 + (cy_curr - cy_prev) ** 2) ** 0.5
            self.speed_estimate = dist


class Tracker:
    """DeepSORT-based multi-object tracker."""

    def __init__(self, class_names: dict = None):
        self.class_names = class_names if class_names is not None else cfg.CLASS_NAMES
        self.tracks: Dict[int, TrackState] = {}
        self.id_mapping: Dict[int, int] = {}  # original_ds_id -> local_override_id
        self.tracker = DeepSort(
            max_age=cfg.MAX_AGE,
            n_init=cfg.MIN_HITS,
            nms_max_overlap=1.0,
            max_cosine_distance=0.2,
            nn_budget=None,
            override_track_class=None,
            embedder="mobilenet",
            half=True,
            bgr=True,
            embedder_gpu=False
        )

    def update(self, detections_xyxy, detections_confidence,
               detections_class_id, frame_bgr=None) -> List[TrackState]:
        """
        Update track states with new detections using DeepSORT.
        Returns list of confirmed TrackState objects.
        """
        # Format for DeepSORT: [[left, top, w, h], confidence, detection_class]
        formatted_detections = []
        for i in range(len(detections_xyxy)):
            x1, y1, x2, y2 = detections_xyxy[i]
            w = x2 - x1
            h = y2 - y1
            conf = detections_confidence[i]
            cls_id = detections_class_id[i]
            formatted_detections.append(([x1, y1, w, h], conf, cls_id))

        # Update tracks
        tracks = self.tracker.update_tracks(formatted_detections, frame=frame_bgr)

        # Sync with internal TrackState
        present_ids = set()
        tracked_objects_list = []

        for track in tracks:
            if not track.is_confirmed():
                continue

            ds_track_id = int(track.track_id)
            track_id = self.id_mapping.get(ds_track_id, ds_track_id)
            present_ids.add(track_id)

            ltwh = track.to_ltwh()
            x1, y1, w, h = ltwh
            x2 = x1 + w
            y2 = y1 + h
            bbox = (x1, y1, x2, y2)

            class_id = track.det_class
            if isinstance(class_id, str):
                try:
                    class_id = int(class_id)
                except ValueError:
                    pass

            class_name = self.class_names.get(class_id, "Unknown")

            if track_id not in self.tracks:
                self.tracks[track_id] = TrackState(track_id)

            self.tracks[track_id].update(bbox, class_id, class_name)
            
            # Extract features for Re-ID (deep_sort_realtime saves features in track.features)
            if hasattr(track, 'features') and track.features and len(track.features) > 0:
                self.tracks[track_id].features = track.features[-1]
            elif hasattr(track, 'embedding') and track.embedding is not None:
                self.tracks[track_id].features = track.embedding

            tracked_objects_list.append(self.tracks[track_id])

        # Cleanup missing tracks
        active_ids = list(self.tracks.keys())
        for tid in active_ids:
            if tid not in present_ids:
                del self.tracks[tid]

        return tracked_objects_list

    def override_current_id(self, current_id: int, new_global_id: int):
        """Hijacks an ID assignment locally. (e.g., Cross-Camera Handoff)"""
        # Store the mapping so future DeepSORT outputs map gracefully
        # Wait, if DeepSORT returns ds_track_id (e.g. 45), we mapped it to 45 initially because it wasn't there.
        # Now current_id IS 45. We map 45 -> new_global_id.
        # So next frame, ds_track_id 45 gets mapped to new_global_id cleanly!
        
        # We need to find what `ds_track_id` mapped to `current_id` if it was already mapped,
        # but normally `current_id` given here IS the newly birthed `ds_track_id`.
        self.id_mapping[current_id] = new_global_id
        if current_id in self.tracks:
            obj = self.tracks.pop(current_id)
            obj.track_id = new_global_id
            self.tracks[new_global_id] = obj
