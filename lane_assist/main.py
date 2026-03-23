"""
main.py

Standalone Lane Assist + Blind Spot Detection Pipeline.
Runs independently using REAR CAMERA.

Optimizations:
    - FP16 half-precision inference
    - Frame skipping (detection every Nth frame)
    - Crop-before-detect (only scan lower 80% of frame)
    - Async threaded detection
    - Model warmup

Usage:
    python -m lane_assist.main --source videos/new.mp4
    python -m lane_assist.main --source 0           # webcam
"""

import cv2
import time
import argparse
import numpy as np
from lane_assist import config
from lane_assist.blind_spot import BlindSpotAnalyzer
from lane_assist.lane_change_advisor import LaneChangeAdvisor
from shared.detector import Detector
from shared.tracker import Tracker
from shared.ui_renderer import UIRenderer
from shared.profiler import ModuleProfiler


def main():
    parser = argparse.ArgumentParser(
        description="Lane Assist + Blind Spot Detection Module")
    parser.add_argument("--source", type=str, default="videos/new.mp4",
                        help="Video file path or camera index (REAR CAMERA)")
    parser.add_argument("--window", type=str, default="",
                        help="Specific window title to capture if --source is screen")
    args = parser.parse_args()

    # ── Initialize Modules ──────────────────────────────────────────────
    det = Detector()
    trk = Tracker()
    bsd = BlindSpotAnalyzer()
    advisor = LaneChangeAdvisor()
    ui = UIRenderer(module_name="Lane Assist • Blind Spot Detection")
    profiler = ModuleProfiler("LaneAssist_BSD")

    # ── Open Video Source ───────────────────────────────────────────────
    use_screen = (args.source == "screen")
    
    if use_screen:
        import mss
        import pygetwindow as gw
        sct = mss.mss()
        window = None
        if args.window:
            try:
                matches = gw.getWindowsWithTitle(args.window)
                if matches:
                    window = matches[0]
                    print(f"[LaneAssist] Capturing specific window: '{window.title}'")
                else:
                    print(f"[LaneAssist] Warning: Window '{args.window}' not found.")
            except Exception:
                pass
        monitor = sct.monitors[1]
        source = "screen"
    else:
        source = int(args.source) if str(args.source).isdigit() else args.source
        cap = cv2.VideoCapture(source)
    
        if not cap.isOpened():
            print(f"[LaneAssist] Error: Cannot open source '{args.source}'")
            return

    W, H = config.BSD_WIDTH, config.BSD_HEIGHT
    scan_line_y = int(H * config.BSD_SCAN_TOP_PCT)  # Top cutoff line
    det_interval = config.DETECTION_INTERVAL

    # Crop region: only scan below the scan line
    crop_region = (0, scan_line_y, W, H)

    print(f"[LaneAssist] Pipeline started. Source: {args.source} (REAR CAMERA)")
    print(f"[LaneAssist] Resolution: {W}x{H} | Detection interval: every {det_interval} frames")
    print(f"[LaneAssist] Scan region: y={scan_line_y} to {H} (top {int(config.BSD_SCAN_TOP_PCT*100)}% ignored)")
    print("[LaneAssist] Press 'q' to exit.\n")

    frame_idx = 0
    # Cache last detections for skipped frames
    last_dets = ([], [], [])
    active_tracks = []
    empty_frames, skip_frames = 0, 0

    while True:
        if use_screen:
            if window:
                monitor = {
                    "top": max(0, window.top),
                    "left": max(0, window.left),
                    "width": window.width,
                    "height": window.height
                }
                if monitor["width"] <= 0 or monitor["height"] <= 0:
                    time.sleep(0.1)
                    continue
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            ret = True
        else:
            ret, frame = cap.read()
    
            if not ret:
                cap.release()
                cap = cv2.VideoCapture(source)
                ret, frame = cap.read()
                if not ret:
                    break

        frame_idx += 1
        profiler.frame_start()

        frame = cv2.resize(frame, (W, H))

        # ── Detection + Tracking (dynamic skipping + crop) ─────────────
        profiler.start_step("Detection")
        if len(last_dets[0]) == 0:
            empty_frames += 1
            skip_frames = min(15, skip_frames + empty_frames // 30)
        else:
            empty_frames, skip_frames = 0, 0

        run_detection = (frame_idx % max(1, skip_frames + det_interval) == 0)

        if run_detection:
            dets_xyxy, dets_conf, dets_cls = det.detect(frame, crop_region=crop_region)
            last_dets = (dets_xyxy, dets_conf, dets_cls)
        else:
            dets_xyxy, dets_conf, dets_cls = last_dets
        profiler.end_step("Detection")

        profiler.start_step("Tracking")
        if run_detection:
            tracks = trk.update(dets_xyxy, dets_conf, dets_cls, frame)
            active_tracks = tracks
        else:
            tracks = active_tracks
        profiler.end_step("Tracking")

        # ── BSD Analysis ───────────────────────────────────────────────
        profiler.start_step("Lane_Logic")
        bsd_frame, cubes, lane_info = bsd.analyze(frame)

        # ── Lane Change Advisory ───────────────────────────────────────
        advisory, details = advisor.analyze(tracks, cubes, lane_info)
        profiler.end_step("Lane_Logic")

        # ── Visualization ──────────────────────────────────────────────
        profiler.start_step("Visualization")
        display = bsd_frame  # BSD already overlays lane on frame

        # Draw scan cutoff line (dashed cyan line at 20% from top)
        for x_start in range(0, W, 20):
            cv2.line(display, (x_start, scan_line_y), (min(x_start + 10, W), scan_line_y),
                     (255, 255, 0), 1, cv2.LINE_AA)
        cv2.putText(display, "SCAN ZONE", (W - 120, scan_line_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1, cv2.LINE_AA)

        # Draw tracked objects
        for obj in tracks:
            if len(obj.history) > 0:
                x1, y1, x2, y2 = obj.history[-1]

                # Determine severity based on blind spot status
                severity = "INFO"
                in_blind_spot = False

                if cubes:
                    point = ((x1 + x2) / 2, y2)
                    if len(cubes) >= 1 and cubes[0] is not None:
                        if cv2.pointPolygonTest(cubes[0], point, False) >= 0:
                            severity = "DANGER"
                            in_blind_spot = True
                    if len(cubes) >= 2 and cubes[1] is not None:
                        if cv2.pointPolygonTest(cubes[1], point, False) >= 0:
                            severity = "DANGER"
                            in_blind_spot = True

                label = f"#{obj.track_id}"
                if in_blind_spot:
                    label += " [BS]"

                ui.draw_bbox(display, x1, y1, x2, y2, label=label,
                             severity=severity, show_glow=in_blind_spot)

        # Alert banners
        warning_text = details.get("warning", "")
        if "UNSAFE" in advisory:
            if warning_text:
                ui.draw_alert_banner(display, f"  {warning_text}",
                                     severity="DANGER")
            else:
                side = advisory.split("_")[-1] if "_" in advisory else ""
                ui.draw_alert_banner(display,
                                     f"BLIND SPOT: {side}",
                                     severity="WARNING")

        # Dashboard
        fps_display = profiler.get_stats().get('avg_fps', 0.0)
        if fps_display == 0.0:
            process_time = time.perf_counter() - profiler._frame_start
            fps_display = 1.0 / max(process_time, 1e-6)

        offset = lane_info['offset'] if lane_info else 0
        road_type = lane_info.get('road_type', 'N/A') if lane_info else 'N/A'
        radius = lane_info.get('radius', 0) if lane_info else 0

        metrics = {
            "Advisory": advisory,
            "Road": road_type,
            "Radius": f"{radius:.0f}m",
            "Offset": f"{offset:.2f}m",
            "Tracks": str(len(tracks)),
        }

        severity_panel = "SAFE"
        if "UNSAFE" in advisory:
            severity_panel = "DANGER"
        elif advisory == "NO_DATA":
            severity_panel = "WARNING"

        ui.compose_dashboard(display, fps_display, severity_panel, metrics)

        # Additional lane metrics at bottom
        if lane_info:
            cv2.putText(display,
                        f"R: {radius:.0f}m  Off: {offset:.2f}m",
                        (W - 250, H - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)

        profiler.end_step("Visualization")

        # ── Profiling ──────────────────────────────────────────────────
        detection_data = {
            "advisory": advisory,
            "tracks": len(tracks),
            "left_occ": details.get("left_occupied", False),
            "right_occ": details.get("right_occupied", False),
        }
        profiler.log_output(detections=detection_data, annotated_frame=display)
        profiler.frame_end()

        # ── Display ───────────────────────────────────────────────────
        cv2.imshow("Lane Assist + Blind Spot Detection", display)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # ── Cleanup ────────────────────────────────────────────────────────
    if not use_screen:
        cap.release()
    cv2.destroyAllWindows()

    profiler.print_summary()
    profiler.export_csv("lane_assist_profile.csv")
    print("[LaneAssist] Pipeline stopped.")


if __name__ == "__main__":
    main()
