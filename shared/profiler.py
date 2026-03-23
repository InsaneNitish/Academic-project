"""
profiler.py

Resource estimation and performance profiling for ADAS modules.
Tracks processing time, data output size, memory usage,
and projects bandwidth/storage requirements for edge deployment.
"""

import time
import csv
import sys
import json
import numpy as np
from collections import deque


class ModuleProfiler:
    """
    Per-module performance and data profiler.

    Usage:
        profiler = ModuleProfiler("FCW")
        while running:
            profiler.frame_start()
            ... process frame ...
            profiler.log_output(detections_list, annotated_frame)
            profiler.frame_end()
        profiler.print_summary()
        profiler.export_csv("fcw_profile.csv")
    """

    def __init__(self, module_name: str, window_size: int = 60):
        self.module_name = module_name
        self.window_size = window_size

        # Per-frame metrics
        self.frame_times = deque(maxlen=window_size)
        self.output_sizes = deque(maxlen=window_size)

        # Cumulative
        self.total_frames = 0
        self.total_time = 0.0
        self.total_output_bytes = 0
        self.start_wall_time = time.time()

        # Current frame
        self._frame_start = 0.0

        # History for CSV export
        self._history = []

        # Step tracking
        self.step_start_times = {}
        self.step_accumulated_time = {}
        self.current_frame_steps = {}

    def start_step(self, step_name: str):
        self.step_start_times[step_name] = time.perf_counter()

    def end_step(self, step_name: str):
        if step_name in self.step_start_times:
            elapsed = time.perf_counter() - self.step_start_times[step_name]
            self.step_accumulated_time[step_name] = self.step_accumulated_time.get(step_name, 0.0) + elapsed
            self.current_frame_steps[step_name] = elapsed * 1000

    def frame_start(self):
        """Call at the beginning of each frame's processing."""
        self._frame_start = time.perf_counter()

    def log_output(self, detections=None, annotated_frame=None, extra_data=None):
        """
        Log the data produced by this frame.
        Args:
            detections: list/dict of detection results
            annotated_frame: the annotated numpy frame (optional)
            extra_data: any additional data dict (warnings, states, etc.)
        """
        output_bytes = 0

        # Detection data size
        if detections is not None:
            try:
                json_str = json.dumps(detections, default=str)
                output_bytes += len(json_str.encode('utf-8'))
            except (TypeError, ValueError):
                output_bytes += sys.getsizeof(detections)

        # Annotated frame size (JPEG-compressed estimate)
        if annotated_frame is not None:
            import cv2
            _, encoded = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            output_bytes += len(encoded)

        # Extra data
        if extra_data is not None:
            try:
                json_str = json.dumps(extra_data, default=str)
                output_bytes += len(json_str.encode('utf-8'))
            except (TypeError, ValueError):
                output_bytes += sys.getsizeof(extra_data)

        self.output_sizes.append(output_bytes)
        self.total_output_bytes += output_bytes

    def frame_end(self):
        """Call at the end of each frame's processing."""
        elapsed = time.perf_counter() - self._frame_start
        self.frame_times.append(elapsed)
        self.total_frames += 1
        self.total_time += elapsed

        # Store history entry
        entry = {
            'frame': self.total_frames,
            'time_ms': elapsed * 1000,
            'output_bytes': self.output_sizes[-1] if self.output_sizes else 0,
            'fps_instant': 1.0 / max(elapsed, 1e-6)
        }
        for k, v in self.current_frame_steps.items():
            entry[f"step_{k}_ms"] = v
        self._history.append(entry)
        self.current_frame_steps.clear()

    # ------------------------------------------------------------------
    # Summary & Export
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get current profiling statistics."""
        elapsed_wall = time.time() - self.start_wall_time
        avg_time = np.mean(self.frame_times) if self.frame_times else 0
        max_time = max(self.frame_times) if self.frame_times else 0
        avg_fps = 1.0 / max(avg_time, 1e-6) if avg_time > 0 else 0

        avg_output = np.mean(self.output_sizes) if self.output_sizes else 0
        data_rate_kbps = (avg_output * avg_fps * 8) / 1024  # kilobits/sec

        return {
            'module': self.module_name,
            'total_frames': self.total_frames,
            'wall_time_sec': round(elapsed_wall, 1),
            'avg_fps': round(avg_fps, 1),
            'avg_frame_time_ms': round(avg_time * 1000, 2),
            'max_frame_time_ms': round(max_time * 1000, 2),
            'avg_output_bytes': int(avg_output),
            'data_rate_kbps': round(data_rate_kbps, 1),
            'data_rate_KBps': round(data_rate_kbps / 8, 1),
            'bandwidth_mbps': round(data_rate_kbps / 1024, 3),
            'storage_MB_per_hour': round((avg_output * avg_fps * 3600) / (1024 * 1024), 1),
            'total_data_MB': round(self.total_output_bytes / (1024 * 1024), 2),
        }

    def print_summary(self):
        """Print formatted profiling summary to console."""
        stats = self.get_stats()
        sep = "=" * 56
        print(f"\n{sep}")
        print(f"  RESOURCE PROFILE: {stats['module']}")
        print(sep)
        print(f"  Total Frames      : {stats['total_frames']}")
        print(f"  Wall Time         : {stats['wall_time_sec']}s")
        print(f"  Avg FPS           : {stats['avg_fps']}")
        print(f"  Avg Frame Time    : {stats['avg_frame_time_ms']} ms")
        print(f"  Max Frame Time    : {stats['max_frame_time_ms']} ms")
        print(f"  ─────────────────────────────────────────")
        print(f"  Avg Output/Frame  : {stats['avg_output_bytes']} bytes")
        print(f"  Data Rate         : {stats['data_rate_KBps']} KB/s ({stats['bandwidth_mbps']} Mbps)")
        print(f"  Storage (1 hour)  : {stats['storage_MB_per_hour']} MB")
        print(f"  Total Data Output : {stats['total_data_MB']} MB")
        if self.step_accumulated_time:
            print(f"  ─────────────────────────────────────────")
            print("  TIME BREAKDOWN (Average per frame):")
            for step, tot_time in self.step_accumulated_time.items():
                avg_step_ms = (tot_time / self.total_frames) * 1000 if self.total_frames > 0 else 0
                print(f"    - {step:<18}: {avg_step_ms:>6.2f} ms")
        print(sep)

    def export_csv(self, filepath: str):
        """Export per-frame profiling data to CSV."""
        if not self._history:
            return

        import os
        os.makedirs("logs", exist_ok=True)
        filepath = os.path.join("logs", os.path.basename(filepath))

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self._history[0].keys())
            writer.writeheader()
            writer.writerows(self._history)

        print(f"[Profiler] Exported {len(self._history)} frames to {filepath}")
