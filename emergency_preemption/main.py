"""
main.py

Standalone Emergency Vehicle Preemption Pipeline.
Detects emergency vehicles using visual (flashing lights) and
optional audio (siren) analysis.

Uses FRONT CAMERA (same as FCW, runs independently for now).

Optimizations:
    - FP16 half-precision inference
    - Frame skipping (detection every Nth frame)
    - Async threaded detection
    - Model warmup

Usage:
    python -m emergency_preemption.main --source videos/video_demo.mp4
    python -m emergency_preemption.main --source 0 --microphone
"""

import cv2
import time
import argparse
import numpy as np
from emergency_preemption import config
from emergency_preemption.visual_detector import EmergencyLightDetector
from emergency_preemption.siren_detector import SirenDetector
from emergency_preemption.preemption_logic import PreemptionEngine
from shared.detector import Detector
from shared.tracker import Tracker
from shared.ui_renderer import UIRenderer
from shared.profiler import ModuleProfiler


def main():
    parser = argparse.ArgumentParser(
        description="Emergency Vehicle Preemption Module")
    parser.add_argument("--source", type=str, default="videos/video_demo.mp4",
                        help="Video file path or camera index (FRONT CAMERA)")
    parser.add_argument("--microphone", action="store_true",
                        help="Enable microphone for siren detection")
    parser.add_argument("--window", type=str, default="",
                        help="Specific window title to capture if --source is screen")
    args = parser.parse_args()

    # ── Initialize Modules ──────────────────────────────────────────────
    det = Detector(model_path="yolo_emergency_model.pt")
    trk = Tracker(class_names=det.class_names)
    light_det = EmergencyLightDetector()
    siren_det = SirenDetector(use_microphone=args.microphone)
    engine = PreemptionEngine()
    ui = UIRenderer(module_name="EVP • Emergency Vehicle Preemption")
    profiler = ModuleProfiler("EmergencyPreemption")

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
                    print(f"[EVP] Capturing specific window: '{window.title}'")
                else:
                    print(f"[EVP] Warning: Window '{args.window}' not found.")
            except Exception as e:
                print(f"[EVP] Window capture error: {e}")
        monitor = sct.monitors[1]  # primary monitor fallback
        source = "screen"
    else:
        source = int(args.source) if str(args.source).isdigit() else args.source
        cap = cv2.VideoCapture(source)
    
        if not cap.isOpened():
            print(f"[EVP] Error: Cannot open source '{args.source}'")
            return

    W, H = config.FRAME_WIDTH, config.FRAME_HEIGHT
    det_interval = config.DETECTION_INTERVAL

    print(f"[EVP] Pipeline started. Source: {args.source} (FRONT CAMERA)")
    print(f"[EVP] Resolution: {W}x{H} | Detection interval: every {det_interval} frames")
    print(f"[EVP] Microphone: {'Enabled' if args.microphone else 'Disabled'}")
    print("[EVP] Press 'q' to exit.\n")

    frame_idx = 0
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
            active_tracks = tracks
        else:
            tracks = active_tracks
        profiler.end_step("Tracking")

        # ── Visual Emergency Light Detection ───────────────────────────
        profiler.start_step("EVP_Logic")
        emergency_vehicles = light_det.analyze(frame, tracks)

        # ── Audio Siren Detection ──────────────────────────────────────
        siren_detected, siren_confidence, audio_details = siren_det.analyze()

        # ── Preemption Decision ────────────────────────────────────────
        state, details = engine.analyze(
            emergency_vehicles, siren_detected, siren_confidence, tracks)
        profiler.end_step("EVP_Logic")

        # ── Visualization ──────────────────────────────────────────────
        profiler.start_step("Visualization")
        # Draw all tracked objects
        for obj in tracks:
            if len(obj.history) > 0:
                x1, y1, x2, y2 = obj.history[-1]

                # Check if this is an emergency vehicle
                is_emergency = any(
                    ev['track_id'] == obj.track_id for ev in emergency_vehicles)

                if is_emergency:
                    ev_info = next(
                        ev for ev in emergency_vehicles
                        if ev['track_id'] == obj.track_id)
                    label = f"EMERGENCY [{ev_info['light_color'].upper()}]"
                    severity = "DANGER"
                    ui.draw_bbox(frame, x1, y1, x2, y2, label=label,
                                 severity=severity, show_glow=True)
                else:
                    label = f"#{obj.track_id} {obj.class_name}"
                    ui.draw_bbox(frame, x1, y1, x2, y2, label=label,
                                 severity="INFO")

        # Alert banners
        if state == "YIELD":
            direction = details.get('approach_direction', '')
            dir_text = f" FROM {direction}" if direction else ""
            ui.draw_alert_banner(
                frame,
                f"EMERGENCY VEHICLE{dir_text} - YIELD!",
                severity="DANGER")
        elif state == "ALERT":
            ui.draw_alert_banner(
                frame,
                "POSSIBLE EMERGENCY VEHICLE DETECTED",
                severity="WARNING")

        # Dashboard
        fps_display = profiler.get_stats().get('avg_fps', 0.0)
        if fps_display == 0.0:
            process_time = time.perf_counter() - profiler._frame_start
            fps_display = 1.0 / max(process_time, 1e-6)

        metrics = {
            "State": state,
            "Score": f"{details['fused_score']:.2f}",
            "Visual": f"{details['visual_score']:.2f}",
            "Audio": f"{details['audio_score']:.2f}",
            "Vehicles": str(len(tracks)),
        }
        if details.get('approach_direction'):
            metrics["Direction"] = details['approach_direction']

        severity_panel = "SAFE"
        if state == "YIELD":
            severity_panel = "DANGER"
        elif state == "ALERT":
            severity_panel = "WARNING"

        ui.compose_dashboard(frame, fps_display, severity_panel, metrics)
        profiler.end_step("Visualization")

        # ── Profiling ──────────────────────────────────────────────────
        detection_data = {
            "state": state,
            "fused_score": details['fused_score'],
            "emergency_count": len(emergency_vehicles),
        }
        profiler.log_output(detections=detection_data, annotated_frame=frame)
        profiler.frame_end()

        # ── Display ───────────────────────────────────────────────────
        cv2.imshow("Emergency Vehicle Preemption", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # ── Cleanup ────────────────────────────────────────────────────────
    if not use_screen:
        cap.release()
    cv2.destroyAllWindows()
    siren_det.release()

    profiler.print_summary()
    profiler.export_csv("evp_profile.csv")
    print("[EVP] Pipeline stopped.")


if __name__ == "__main__":
    main()
