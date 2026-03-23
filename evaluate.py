"""
evaluate.py

Interactive Evaluation Tool for ADAS Modules.
Annotate frames and compute Precision, Recall, F1, Accuracy.

Usage:
    python evaluate.py --module lane --source videos/new.mp4        (rear camera - BSD lane)
    python evaluate.py --module lane_fcw --source videos/new1.mp4   (front camera - Hough lane)
    python evaluate.py --module bsd --source videos/new.mp4         (rear camera - blind spot)
    python evaluate.py --module fcw --source videos/new1.mp4        (front camera - collision)

Controls:
    1 = Correct Detection (True Positive)
    2 = False Positive (wrong detection)
    3 = Missed Detection (False Negative)
    0 = Skip (no object present, True Negative)
    q = Quit and show results
"""

import cv2
import csv
import json
import time
import argparse
import numpy as np
from datetime import datetime


def sample_frames(video_path, num_samples=200):
    """Extract evenly spaced frames from video."""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        print("[Eval] Error: Cannot read video.")
        return []

    step = max(1, total_frames // num_samples)
    frames = []

    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append((i, frame))
        if len(frames) >= num_samples:
            break

    cap.release()
    print(f"[Eval] Sampled {len(frames)} frames from {total_frames} total.")
    return frames


def run_lane_evaluation(frame, frame_idx, bsd):
    """Run lane detection using BlindSpotAnalyzer (rear camera / bird's eye view)."""
    from lane_assist import config
    frame_resized = cv2.resize(frame, (config.BSD_WIDTH, config.BSD_HEIGHT))

    bsd_frame, cubes, lane_info = bsd.analyze(frame_resized)
    display = bsd_frame

    # Show lane info on screen
    if lane_info:
        road = lane_info.get('road_type', 'N/A')
        radius = lane_info.get('radius', 0)
        offset = lane_info.get('offset', 0)
        cv2.putText(display, f"Road: {road}  R: {radius:.0f}m  Off: {offset:.2f}m",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(display, "LANE DETECTED", (250, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    else:
        cv2.putText(display, "NO LANE DETECTED", (220, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    cv2.putText(display, f"Frame {frame_idx} | LANE DETECTION (Rear Camera)",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(display, "1=Correct  2=FalsePositive  3=Missed  0=N/A  q=Quit",
                (10, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    return display


def run_lane_fcw_evaluation(frame, frame_idx, la):
    """Run lane detection using Hough Transform (front camera)."""
    frame_resized = cv2.resize(frame, (640, 480))
    drivable_mask, lane_poly = la.analyze(frame_resized)

    display = frame_resized.copy()

    if drivable_mask is not None:
        green_overlay = np.zeros_like(display)
        green_overlay[:, :] = (0, 200, 0)
        mask_bool = drivable_mask > 0
        display[mask_bool] = cv2.addWeighted(
            display, 0.6, green_overlay, 0.4, 0)[mask_bool]

    if lane_poly is not None:
        cv2.polylines(display, [lane_poly], True, (0, 255, 255), 2)

    cv2.putText(display, f"Frame {frame_idx} | LANE DETECTION (Front Camera)",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(display, "1=Correct  2=FalsePositive  3=Missed  0=N/A  q=Quit",
                (10, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    return display


def run_bsd_evaluation(frame, frame_idx, det, trk, bsd):
    """Run blind spot detection and show result for annotation."""
    from lane_assist import config

    frame_resized = cv2.resize(frame, (config.BSD_WIDTH, config.BSD_HEIGHT))
    scan_line_y = int(config.BSD_HEIGHT * config.BSD_SCAN_TOP_PCT)

    # Detection
    crop_region = (0, scan_line_y, config.BSD_WIDTH, config.BSD_HEIGHT)
    dets_xyxy, dets_conf, dets_cls = det.detect(frame_resized, crop_region=crop_region)
    tracks = trk.update(dets_xyxy, dets_conf, dets_cls, frame_resized)

    # BSD
    bsd_frame, cubes, lane_info = bsd.analyze(frame_resized)
    display = bsd_frame

    # Draw tracked vehicles
    for obj in tracks:
        if len(obj.history) > 0:
            x1, y1, x2, y2 = map(int, obj.history[-1])
            in_bs = False
            if cubes:
                pt = ((x1 + x2) / 2, y2)
                for cube in cubes:
                    if cube is not None and cv2.pointPolygonTest(cube, pt, False) >= 0:
                        in_bs = True
                        break

            color = (0, 0, 255) if in_bs else (0, 255, 0)
            label = f"#{obj.track_id} {'[BS]' if in_bs else ''}"
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
            cv2.putText(display, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # Scan line
    cv2.line(display, (0, scan_line_y), (config.BSD_WIDTH, scan_line_y),
             (255, 255, 0), 1)

    cv2.putText(display, f"Frame {frame_idx} | BLIND SPOT DETECTION",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(display, "1=Correct  2=FalsePositive  3=Missed  0=N/A  q=Quit",
                (10, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    return display


def run_fcw_evaluation(frame, frame_idx, det, trk, fcw_engine, la, eng):
    """Run FCW and show result for annotation."""
    from fcw import config

    frame_resized = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))

    dets_xyxy, dets_conf, dets_cls = det.detect(frame_resized)
    tracks = trk.update(dets_xyxy, dets_conf, dets_cls, frame_resized)

    drivable_mask, lane_poly = la.analyze(frame_resized)
    fps_val = 30.0
    fcw_state, fcw_target_id, fcw_ttc = fcw_engine.analyze(tracks, lane_poly, fps_val)

    display = frame_resized.copy()

    # Draw detections
    for obj in tracks:
        if len(obj.history) > 0:
            x1, y1, x2, y2 = map(int, obj.history[-1])
            is_target = (fcw_target_id and obj.track_id == fcw_target_id)
            color = (0, 0, 255) if is_target else (0, 255, 0)
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
            label = f"#{obj.track_id}"
            if is_target:
                label += f" TTC:{fcw_ttc:.1f}s" if fcw_ttc and fcw_ttc < 99 else ""
            cv2.putText(display, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # FCW state banner
    state_colors = {"SAFE": (0, 200, 0), "WARNING": (0, 180, 255), "DANGER": (0, 0, 255)}
    cv2.putText(display, f"FCW: {fcw_state}",
                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                state_colors.get(fcw_state, (255, 255, 255)), 2)

    cv2.putText(display, f"Frame {frame_idx} | FCW EVALUATION",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(display, "1=Correct  2=FalsePositive  3=Missed  0=N/A  q=Quit",
                (10, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    return display


def compute_metrics(annotations):
    """Compute precision, recall, F1, accuracy from annotations."""
    tp = annotations.count("TP")
    fp = annotations.count("FP")
    fn = annotations.count("FN")
    tn = annotations.count("TN")
    total = len(annotations)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / total if total > 0 else 0

    return {
        "Total Frames": total,
        "True Positives (TP)": tp,
        "False Positives (FP)": fp,
        "False Negatives (FN)": fn,
        "True Negatives (TN)": tn,
        "Precision": round(precision, 4),
        "Recall": round(recall, 4),
        "F1 Score": round(f1, 4),
        "Accuracy": round(accuracy, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="ADAS Evaluation Tool")
    parser.add_argument("--module", type=str, required=True,
                        choices=["lane", "lane_fcw", "bsd", "fcw"],
                        help="Module to evaluate: lane, bsd, or fcw")
    parser.add_argument("--source", type=str, required=True,
                        help="Video file path")
    parser.add_argument("--samples", type=int, default=200,
                        help="Number of frames to sample (default: 200)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  EVALUATION TOOL: {args.module.upper()}")
    print(f"  Source: {args.source}")
    print(f"  Samples: {args.samples}")
    print(f"{'='*60}\n")

    # Sample frames
    frames = sample_frames(args.source, args.samples)
    if not frames:
        return

    # Initialize modules based on selection
    if args.module == "lane":
        from lane_assist.blind_spot import BlindSpotAnalyzer
        bsd = BlindSpotAnalyzer()
    elif args.module == "lane_fcw":
        from fcw.lane_analyzer import LaneAnalyzer
        la = LaneAnalyzer()
    elif args.module == "bsd":
        from shared.detector import Detector
        from shared.tracker import Tracker
        from lane_assist.blind_spot import BlindSpotAnalyzer
        det = Detector()
        trk = Tracker()
        bsd = BlindSpotAnalyzer()
    elif args.module == "fcw":
        from shared.detector import Detector
        from shared.tracker import Tracker
        from fcw.lane_analyzer import LaneAnalyzer
        from fcw.traffic_engine import TrafficEngine
        from fcw.collision import FCWEngine
        det = Detector()
        trk = Tracker()
        la = LaneAnalyzer()
        eng = TrafficEngine()
        fcw_engine = FCWEngine()

    annotations = []
    frame_labels = []

    print("Starting evaluation. Press keys to annotate each frame:\n")
    print("  1 = Correct Detection (True Positive)")
    print("  2 = False Positive (system detected something wrong)")
    print("  3 = Missed Detection (system missed something)")
    print("  0 = No object present / Not applicable (True Negative)")
    print("  q = Quit early\n")

    for idx, (fnum, frame) in enumerate(frames):
        # Process frame
        if args.module == "lane":
            display = run_lane_evaluation(frame, fnum, bsd)
        elif args.module == "lane_fcw":
            display = run_lane_fcw_evaluation(frame, fnum, la)
        elif args.module == "bsd":
            display = run_bsd_evaluation(frame, fnum, det, trk, bsd)
        elif args.module == "fcw":
            display = run_fcw_evaluation(frame, fnum, det, trk, fcw_engine, la, eng)

        # Progress bar
        progress = f"[{idx+1}/{len(frames)}]"
        cv2.putText(display, progress, (530, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow(f"Evaluate: {args.module.upper()}", display)

        # Wait for key
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key == ord('1'):
                annotations.append("TP")
                frame_labels.append({"frame": fnum, "label": "TP"})
                break
            elif key == ord('2'):
                annotations.append("FP")
                frame_labels.append({"frame": fnum, "label": "FP"})
                break
            elif key == ord('3'):
                annotations.append("FN")
                frame_labels.append({"frame": fnum, "label": "FN"})
                break
            elif key == ord('0'):
                annotations.append("TN")
                frame_labels.append({"frame": fnum, "label": "TN"})
                break
            elif key == ord('q'):
                print("\n[Eval] Quit early.")
                break
        else:
            continue
        if key == ord('q'):
            break

    cv2.destroyAllWindows()

    # ── Results ─────────────────────────────────────────────────────────
    if not annotations:
        print("[Eval] No annotations collected.")
        return

    metrics = compute_metrics(annotations)

    print(f"\n{'='*60}")
    print(f"  EVALUATION RESULTS: {args.module.upper()}")
    print(f"{'='*60}")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25}: {v:.4f} ({v*100:.1f}%)")
        else:
            print(f"  {k:<25}: {v}")
    print(f"{'='*60}\n")

    # ── Save Results ────────────────────────────────────────────────────
    import os
    os.makedirs("eval_results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join("eval_results", f"eval_{args.module}_{timestamp}.json")
    csv_file = os.path.join("eval_results", f"eval_{args.module}_{timestamp}.csv")

    # JSON summary
    output = {
        "module": args.module,
        "source": args.source,
        "timestamp": timestamp,
        "total_sampled": len(frames),
        "total_annotated": len(annotations),
        "metrics": metrics,
        "annotations": frame_labels
    }
    with open(results_file, "w") as f:
        json.dump(output, f, indent=2)

    # CSV for paper tables
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value", "Percentage"])
        for k, v in metrics.items():
            if isinstance(v, float):
                writer.writerow([k, f"{v:.4f}", f"{v*100:.1f}%"])
            else:
                writer.writerow([k, v, ""])

    print(f"[Eval] Results saved to:")
    print(f"  JSON: {results_file}")
    print(f"  CSV:  {csv_file}")


if __name__ == "__main__":
    main()
