"""
main.py

Standalone Forward Collision Warning (FCW) Pipeline.
Runs independently using FRONT CAMERA only.

Features:
    - Ego-path based in-corridor filtering (no lane detection needed)
    - Class-specific distance estimation (car/bus/truck/motorcycle)
    - Regression-based TTC over 8 frames
    - Context-aware traffic rules (vehicle count thresholds)
    - Frame skipping (YOLO every 3rd frame)

Usage:
    python -m fcw.main --source videos/new1.mp4
    python -m fcw.main --source 0           # webcam
"""

import cv2
import time
import csv
import argparse
import numpy as np
from fcw import config
from fcw.collision import FCWEngine, estimate_distance
from fcw.ego_path import get_ego_polygon, is_in_ego_path
from shared.detector import Detector
from shared.tracker import Tracker
from shared.ui_renderer import UIRenderer
from shared.profiler import ModuleProfiler


def main():
    parser = argparse.ArgumentParser(description="FCW Module - Forward Collision Warning")
    parser.add_argument("--source", type=str, default="videos/new1.mp4",
                        help="Video file path or camera index (FRONT CAMERA)")
    parser.add_argument("--window", type=str, default="",
                        help="Specific window title to capture if --source is screen")
    args = parser.parse_args()

    # ── Initialize Modules ──────────────────────────────────────────────
    det = Detector()
    trk = Tracker()
    fcw_engine = FCWEngine()
    ui = UIRenderer(module_name="FCW • Forward Collision Warning")
    profiler = ModuleProfiler("FCW")

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
                    print(f"[FCW] Capturing specific window: '{window.title}'")
                else:
                    print(f"[FCW] Warning: Window '{args.window}' not found.")
            except Exception:
                pass
        monitor = sct.monitors[1]
        source = "screen"
    else:
        source = int(args.source) if str(args.source).isdigit() else args.source
        cap = cv2.VideoCapture(source)
    
        if not cap.isOpened():
            print(f"[FCW] Error: Cannot open source '{args.source}'")
            return

    W, H = config.FRAME_WIDTH, config.FRAME_HEIGHT
    det_interval = config.DETECTION_INTERVAL
    print(f"[FCW] Pipeline started. Source: {args.source} (FRONT CAMERA)")
    print(f"[FCW] Resolution: {W}x{H} | Detection interval: every {det_interval} frames")
    print(f"[FCW] Traffic thresholds: moderate >= {config.TRAFFIC_MODERATE_THRESHOLD}, heavy >= {config.TRAFFIC_HEAVY_THRESHOLD}")
    print("[FCW] Press 'q' to exit.\n")

    # Precompute ego path polygon for visualization
    ego_poly = get_ego_polygon(W, H)

    # ── Logging ─────────────────────────────────────────────────────────
    import os
    os.makedirs("logs", exist_ok=True)
    log_file = open(os.path.join("logs", "fcw_log.csv"), "w", newline="")
    csv_writer = csv.writer(log_file)
    csv_writer.writerow(["Timestamp", "Frame", "Vehicles", "Traffic",
                         "FCW_State", "TTC", "Distance_m"])

    frame_idx = 0
    last_dets = ([], [], [])
    last_tracks = []
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

        # ── Detection + Tracking (dynamic skipping) ────────────────────
        profiler.start_step("Detection")
        if len(last_dets[0]) == 0:
            empty_frames += 1
            skip_frames = min(15, skip_frames + empty_frames // 30)
        else:
            empty_frames, skip_frames = 0, 0

        run_detection = (frame_idx % max(1, skip_frames + det_interval) == 0)

        if run_detection:
            # Mask out the bottom 10% of the image (ego hood)
            crop_region = (0, 0, W, int(H * 0.9))
            dets_xyxy, dets_conf, dets_cls = det.detect(frame, crop_region=crop_region)
            last_dets = (dets_xyxy, dets_conf, dets_cls)
        else:
            dets_xyxy, dets_conf, dets_cls = last_dets
        profiler.end_step("Detection")
        
        profiler.start_step("Tracking")
        if run_detection:
            tracks = trk.update(dets_xyxy, dets_conf, dets_cls, frame)
            last_tracks = tracks
        else:
            tracks = last_tracks
        profiler.end_step("Tracking")

        # ── Traffic Context ────────────────────────────────────────────
        if use_screen:
            fps_val = 30.0
        else:
            fps_val = cap.get(cv2.CAP_PROP_FPS)
            
        if fps_val == 0:
            fps_val = 30.0

        vehicle_count = len(tracks)

        if vehicle_count >= config.TRAFFIC_HEAVY_THRESHOLD:
            traffic_level = "HEAVY"
        elif vehicle_count >= config.TRAFFIC_MODERATE_THRESHOLD:
            traffic_level = "MODERATE"
        else:
            traffic_level = "FREE"

        # ── FCW Decision (ego-path based) ──────────────────────────────
        fcw_state, fcw_target_id, fcw_ttc, distances = fcw_engine.analyze(
            tracks, W, H, fps_val, vehicle_count)
        profiler.end_step("FCW_Logic")

        # ── Visualization ──────────────────────────────────────────────
        profiler.start_step("Visualization")
        # Ego path overlay (subtle translucent corridor)
        ui.draw_lane_overlay(frame, poly=ego_poly,
                             color=(80, 200, 80), alpha=0.15)

        # Bounding boxes with distance + TTC
        pedestrian_danger = False
        for obj in tracks:
            if len(obj.history) == 0:
                continue

            x1, y1, x2, y2 = obj.history[-1]
            bbox_h = max(1, y2 - y1)
            class_id = getattr(obj, 'class_id', 2)

            dist_m = estimate_distance(bbox_h, class_id)

            severity = "INFO"
            glow = False

            in_path = obj.track_id in distances

            if in_path:
                severity = "SAFE"

            if fcw_target_id is not None and obj.track_id == fcw_target_id:
                if fcw_state == "DANGER":
                    severity = "DANGER"
                    glow = True
                    if class_id == 0:
                        pedestrian_danger = True
                elif fcw_state == "WARNING":
                    severity = "WARNING"
                    glow = True

            # Build cleaner label (no track IDs)
            label = ""
            if obj.track_id in distances:
                label = f"{dist_m:.0f}m"
                d_info = distances[obj.track_id]
                ttc_val = d_info[1]
                if ttc_val is not None and ttc_val < config.TTC_MAX_DISPLAY:
                    label += f" | {ttc_val:.1f}s"

            ui.draw_bbox(frame, x1, y1, x2, y2, label=label,
                         severity=severity, show_glow=glow)

        # Full-screen red flash for pedestrian danger
        if pedestrian_danger:
            red_overlay = np.zeros_like(frame)
            red_overlay[:, :] = (0, 0, 255)  # BGR Red
            cv2.addWeighted(red_overlay, 0.3, frame, 0.7, 0, frame)
            
            text = "PEDESTRIAN IN PATH!"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)[0]
            cx = (W - text_size[0]) // 2
            cy = H // 2
            cv2.putText(frame, text, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)

        # Alert banners
        if fcw_state == "DANGER":
            ttc_str = f"{fcw_ttc:.1f}s" if fcw_ttc and fcw_ttc < 99 else ""
            dist_str = ""
            if fcw_target_id in distances:
                dist_str = f"  {distances[fcw_target_id][0]:.0f}m"
            ui.draw_alert_banner(frame,
                                 f"COLLISION WARNING  TTC: {ttc_str}{dist_str}",
                                 severity="DANGER")
        elif fcw_state == "WARNING":
            ttc_str = f"{fcw_ttc:.1f}s" if fcw_ttc and fcw_ttc < 99 else ""
            ui.draw_alert_banner(frame,
                                 f"KEEP DISTANCE  TTC: {ttc_str}",
                                 severity="WARNING")

        # Dashboard
        fps_display = profiler.get_stats().get('avg_fps', 0.0)
        if fps_display == 0.0:
            process_time = time.perf_counter() - profiler._frame_start
            fps_display = 1.0 / max(process_time, 1e-6)

        metrics = {
            "State": fcw_state,
            "TTC": f"{fcw_ttc:.1f}s" if fcw_ttc else "N/A",
            "Traffic": traffic_level,
        }

        severity_panel = "SAFE"
        if fcw_state == "DANGER":
            severity_panel = "DANGER"
        elif fcw_state == "WARNING":
            severity_panel = "WARNING"

        ui.compose_dashboard(frame, fps_display, severity_panel, metrics)
        profiler.end_step("Visualization")

        # ── Profiling ──────────────────────────────────────────────────
        target_dist = ""
        if fcw_target_id in distances:
            target_dist = f"{distances[fcw_target_id][0]:.1f}"

        detection_data = {
            "vehicles": vehicle_count,
            "fcw_state": fcw_state,
            "traffic": traffic_level
        }
        profiler.log_output(detections=detection_data, annotated_frame=frame)
        profiler.frame_end()

        # ── Logging ────────────────────────────────────────────────────
        csv_writer.writerow([
            time.time(), frame_idx,
            vehicle_count, traffic_level,
            fcw_state,
            f"{fcw_ttc:.1f}" if fcw_ttc and fcw_ttc < 99 else "",
            target_dist
        ])

        # ── Display ───────────────────────────────────────────────────
        cv2.imshow("FCW - Forward Collision Warning", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # ── Cleanup ────────────────────────────────────────────────────────
    if not use_screen:
        cap.release()
    cv2.destroyAllWindows()
    log_file.close()

    profiler.print_summary()
    profiler.export_csv("fcw_profile.csv")
    print("[FCW] Pipeline stopped.")


if __name__ == "__main__":
    main()
