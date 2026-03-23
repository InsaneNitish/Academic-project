import cv2
import time
import argparse
import numpy as np
import torch

# Import configurations
from fcw import config as fcw_config

# Import shared modules
from shared.detector import Detector
from shared.tracker import Tracker
from shared.ui_renderer import UIRenderer
from shared.profiler import ModuleProfiler

# Import specific module engines
from fcw.collision import FCWEngine
from fcw.ego_path import get_ego_polygon
from emergency_preemption.visual_detector import EmergencyLightDetector
from emergency_preemption.siren_detector import SirenDetector
from emergency_preemption.preemption_logic import PreemptionEngine
from lane_assist.blind_spot import BlindSpotAnalyzer
from lane_assist.lane_change_advisor import LaneChangeAdvisor
from shared.global_track_manager import GlobalTrackManager

def main():
    parser = argparse.ArgumentParser(description="Unified ADAS Module (FCW + EVP + BSD)")
    parser.add_argument("--source_front", type=str, default="videos/test3.mp4", help="Front camera feed")
    parser.add_argument("--source_rear", type=str, default="videos/new.mp4", help="Rear camera feed")
    args = parser.parse_args()

    print("[Unified] Loading True Dual-Model Unified Pipeline...")
    
    if not torch.cuda.is_available():
        print("\n\n[WARNING] PyTorch cannot detect a CUDA GPU! You requested GPU performance, but your PyTorch library is CPU-only.")
        print("          To fix this, install GPU-enabled PyTorch by running:")
        print("          pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        print("          Proceeding extremely slowly on CPU for now...\n\n")

    # 1. Main Detector (for FCW and Lane Assist) -> General Traffic
    det_main = Detector(model_path="yolov8n.pt")
    trk_front = Tracker(class_names=det_main.class_names)
    trk_rear  = Tracker(class_names=det_main.class_names)
    
    # 2. EVP Detector (for Emergency Preemption ONLY) -> Ambulances
    det_evp = Detector(model_path="yolo_emergency_model.pt")
    trk_evp = Tracker(class_names=det_evp.class_names)
    
    fcw_engine = FCWEngine()
    
    light_det = EmergencyLightDetector()
    siren_det = SirenDetector(use_microphone=False)
    evp_engine = PreemptionEngine()
    
    bsd_engine = BlindSpotAnalyzer()
    advisor = LaneChangeAdvisor()
    gtm = GlobalTrackManager(time_window=6.0, cosine_threshold=0.25)

    ui = UIRenderer(module_name="FRONT: FCW + EVP (Dual AI)")
    ui_rear = UIRenderer(module_name="REAR: Lane Assist + Blind Spot")
    profiler = ModuleProfiler("Unified_Tri_Staggered")

    cap_f = cv2.VideoCapture(args.source_front)
    cap_r = cv2.VideoCapture(args.source_rear)

    if not cap_f.isOpened() or not cap_r.isOpened():
        print("Cannot open one of the video sources.")
        return

    W, H_f = 640, 360  # Front resolution
    H_r = 480          # Rear resolution (Lane Assist relies on 480p math)
    det_interval = 3

    print(f"[Unified] Pipeline started. Press 'q' to exit.")

    frame_idx = 0
    last_dets_f = ([], [], [])
    last_dets_r = ([], [], [])
    last_dets_evp = ([], [], [])

    # Dynamic Skipping Counters (saves CPU on empty roads!)
    empty_f, skip_f = 0, 0
    empty_r, skip_r = 0, 0
    empty_evp, skip_evp = 0, 0

    active_rear_tracks = {}
    active_front_tracks = {}
    passing_vehicles = {}

    while True:
        ret_f, frame_f = cap_f.read()
        ret_r, frame_r = cap_r.read()

        if not ret_f or not ret_r:
            print("Video streams ended.")
            break

        frame_idx += 1
        profiler.frame_start()
        
        frame_f = cv2.resize(frame_f, (W, H_f))
        frame_r = cv2.resize(frame_r, (W, H_r))

        run_front_det = (frame_idx % det_interval == 0)
        run_rear_det  = (frame_idx % det_interval == 1)
        run_evp_det   = (frame_idx % det_interval == 2)

        # FRONT CAMERA DYNAMIC EXECUTION
        if run_front_det:
            if skip_f > 0:
                skip_f -= 1
                last_dets_f = ([], [], []) # Feed empty to tracker
            else:
                crop_region_f = (0, 0, W, int(H_f * 0.9))
                last_dets_f = det_main.detect(frame_f, crop_region=crop_region_f)
                if len(last_dets_f[0]) == 0:
                    empty_f += 1
                    if empty_f >= 2: # 6 empty frames (2 runs) -> Skip next 6
                        skip_f, empty_f = 2, 0 
                else: 
                    empty_f = 0

        # REAR CAMERA DYNAMIC EXECUTION
        if run_rear_det:
            if skip_r > 0:
                skip_r -= 1
                last_dets_r = ([], [], [])
            else:
                scan_line_y = int(H_r * 0.2)
                last_dets_r = det_main.detect(frame_r, crop_region=(0, scan_line_y, W, H_r))
                if len(last_dets_r[0]) == 0:
                    empty_r += 1
                    if empty_r >= 2:
                        skip_r, empty_r = 2, 0
                else:
                    empty_r = 0

        # EMERGENCY CAMERA DYNAMIC EXECUTION
        if run_evp_det:
            if skip_evp > 0:
                skip_evp -= 1
                last_dets_evp = ([], [], [])
            else:
                crop_region_f = (0, 0, W, int(H_f * 0.9))
                last_dets_evp = det_evp.detect(frame_f, crop_region=crop_region_f)
                if len(last_dets_evp[0]) == 0:
                    empty_evp += 1
                    if empty_evp >= 2:
                        skip_evp, empty_evp = 2, 0
                else:
                    empty_evp = 0

        # --- 2. MULTI-TRACKING ---
        tracks_f   = trk_front.update(last_dets_f[0], last_dets_f[1], last_dets_f[2], frame_f)
        tracks_r   = trk_rear.update(last_dets_r[0], last_dets_r[1], last_dets_r[2], frame_r)
        tracks_evp = trk_evp.update(last_dets_evp[0], last_dets_evp[1], last_dets_evp[2], frame_f)

        # Handle Rear-exit passing logic
        current_time = time.time()
        current_rear_tracks = {obj.track_id: obj for obj in tracks_r}
        for trk_id, obj in active_rear_tracks.items():
            if trk_id not in current_rear_tracks:
                if len(obj.history) > 0:
                    x1, y1, x2, y2 = obj.history[-1]
                    # If it exits sides or bottom of rear camera, it is an overtaking car
                    if y2 > H_r * 0.85 or x1 < W * 0.1 or x2 > W * 0.9:
                        passing_vehicles[trk_id] = current_time
                        print(f"[LOG] Vehicle ID {trk_id} over-took from rear. Entering blind-spot gap.")
                        gtm.register_exited_vehicle(trk_id, getattr(obj, 'features', None))
        
        active_rear_tracks = current_rear_tracks
        passing_vehicles = {k: v for k, v in passing_vehicles.items() if current_time - v < 4.0}

        # Handle Front-entry Re-ID matching logic
        current_front_tracks = {obj.track_id: obj for obj in tracks_f}
        for trk_id, obj in current_front_tracks.items():
            if trk_id not in active_front_tracks:
                if len(obj.history) > 0:
                    _, _, _, y2 = obj.history[-1]
                    # New object appeared in the bottom half of the screen
                    if y2 > H_f * 0.5:
                        matched_id = gtm.match_entered_vehicle(getattr(obj, 'features', None))
                        if matched_id is not None:
                            print(f"[RE-ID] MATCH! Front vehicle {trk_id} adopted Rear vehicle ID {matched_id}.")
                            trk_front.override_current_id(trk_id, matched_id)
                            obj.track_id = matched_id
                            # Remove the passing warning immediately
                            if matched_id in passing_vehicles:
                                del passing_vehicles[matched_id]
        
        active_front_tracks = {obj.track_id: obj for obj in tracks_f}

        fps_val = cap_f.get(cv2.CAP_PROP_FPS) or 30.0

        # --- 3. FRONT CAMERA LOGIC (FCW + EVP) ---
        vehicle_count = len(tracks_f)
        traffic_level = "HEAVY" if vehicle_count >= 8 else "MODERATE" if vehicle_count >= 4 else "FREE"
        ego_poly = get_ego_polygon(W, H_f)
        # FCW runs cleanly on det_main tracks
        fcw_state, fcw_target_id, fcw_ttc, distances = fcw_engine.analyze(tracks_f, W, H_f, fps_val, vehicle_count)

        # EVP runs entirely on its own tracking stream (tracks_evp)
        emergency_vehicles = light_det.analyze(frame_f, tracks_evp)
        siren_detected, siren_confidence, _ = siren_det.analyze()
        evp_state, evp_details = evp_engine.analyze(emergency_vehicles, siren_detected, siren_confidence, tracks_evp)

        # --- 4. REAR CAMERA LOGIC (Lane Assist / BSD) ---
        bsd_frame, cubes, lane_info = bsd_engine.analyze(frame_r)
        advisory, bsd_details = advisor.analyze(tracks_r, cubes, lane_info)

        # ==========================================
        # VISUALIZATION - FRONT (Draw FCW + Overwrite with EVP)
        # ==========================================
        display_f = frame_f.copy()
        ui.draw_lane_overlay(display_f, poly=ego_poly, color=(80, 200, 80), alpha=0.1)

        pedestrian_danger_f = False
        
        # 1. Draw Normal Traffic
        for obj in tracks_f:
            if not obj.history: continue
            x1, y1, x2, y2 = obj.history[-1]
            class_id = getattr(obj, 'class_id', 2)
            in_fcw_path = obj.track_id in distances
            
            severity, glow, label = "INFO", False, ""
            if in_fcw_path:
                dist_m = (fcw_config.REAL_HEIGHTS.get(class_id, 1.5) * fcw_config.FOCAL_LENGTH_PX) / max(1, y2 - y1)
                ttc_val = distances[obj.track_id][1]
                
                if ttc_val is not None and ttc_val < getattr(fcw_config, 'TTC_MAX_DISPLAY', 9.9):
                    label = f"{dist_m:.0f}m | {ttc_val:.1f}s"
                else:
                    label = f"{dist_m:.0f}m"
                
                severity = "SAFE"
                if fcw_target_id == obj.track_id:
                    if fcw_state in ["WARNING", "DANGER"]:
                        severity, glow = fcw_state, True
                        if class_id == 0: pedestrian_danger_f = True

            ui.draw_bbox(display_f, x1, y1, x2, y2, label=label.strip(), severity=severity, show_glow=glow)

        # 2. Draw Emergency Vehicles OVER the traffic
        for obj in tracks_evp:
            if not obj.history: continue
            x1, y1, x2, y2 = obj.history[-1]
            is_evp = any(c in obj.class_name.lower() for c in ['ambulance', 'fire_truck', 'police'])
            
            if is_evp:
                label = f"EMERGENCY ({obj.class_name})"
                ui.draw_bbox(display_f, x1, y1, x2, y2, label=label, severity="WARNING", show_glow=True)

        if pedestrian_danger_f:
            red_overlay = np.zeros_like(display_f)
            red_overlay[:, :] = (0, 0, 255)
            cv2.addWeighted(red_overlay, 0.3, display_f, 0.7, 0, display_f)
            text = "PEDESTRIAN IN PATH!"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)[0]
            cv2.putText(display_f, text, ((W - text_size[0]) // 2, H_f // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)

        if evp_state == "YIELD": ui.draw_alert_banner(display_f, "YIELD: EMERGENCY VEHICLE APPROACHING", severity="DANGER")
        elif pedestrian_danger_f: ui.draw_alert_banner(display_f, "DANGER: PEDESTRIAN IN PATH", severity="DANGER")
        elif fcw_state == "DANGER": ui.draw_alert_banner(display_f, f"COLLISION WARNING TTC: {fcw_ttc:.1f}s", severity="DANGER")
        elif fcw_state == "WARNING": ui.draw_alert_banner(display_f, "KEEP DISTANCE", severity="WARNING")

        # ==========================================
        # VISUALIZATION - REAR
        # ==========================================
        display_r = bsd_frame
        for obj in tracks_r:
            if not obj.history: continue
            x1, y1, x2, y2 = obj.history[-1]
            
            in_blind_spot = False
            if cubes:
                pt = ((x1+x2)/2, y2)
                for cube in cubes:
                    if cube is not None and cv2.pointPolygonTest(cube, pt, False) >= 0:
                        in_blind_spot = True

            severity, glow, label = ("DANGER", True, "[BLIND SPOT]") if in_blind_spot else ("INFO", False, "")
            ui_rear.draw_bbox(display_r, x1, y1, x2, y2, label=label, severity=severity, show_glow=glow)

        if "UNSAFE" in advisory:
            ui_rear.draw_alert_banner(display_r, "BLIND SPOT: DO NOT CHANGE LANES", severity="WARNING")
        elif passing_vehicles:
            # Show a soft warning that a vehicle is currently in the gap
            ui_rear.draw_alert_banner(display_r, f"PASSING VEHICLE IN MIDDLE GAP ({len(passing_vehicles)})", severity="WARNING")

        # --- Dashboards ---
        process_time = time.perf_counter() - profiler._frame_start
        fps_curr = 1.0 / max(process_time, 1e-6)
        
        ui.compose_dashboard(display_f, fps_curr, "DANGER" if fcw_state=="DANGER" else "SAFE", {"FCW": fcw_state, "EVP": evp_state, "Traffic": traffic_level}, bottom_badge=True)
        
        vehicle_count_r = len(tracks_r)
        traffic_level_r = "HEAVY" if vehicle_count_r >= 6 else "MODERATE" if vehicle_count_r >= 3 else "FREE"
        ui_rear.compose_dashboard(display_r, fps_curr, "WARNING" if "UNSAFE" in advisory else "SAFE", {"Lane Advice": advisory, "Traffic": traffic_level_r, "Offset": f"{lane_info.get('offset', 0):.2f}m" if lane_info else "N/A"}, bottom_badge=False)

        # Prepare combined display
        display_r_resized = cv2.resize(display_r, (W, H_f))
        combined = np.hstack([display_f, display_r_resized])
        h, w = combined.shape[:2]
        display_combined = cv2.resize(combined, (w, h))

        # --- LOG DATA & FINISH FRAME ---
        log_data = {
            "fcw_state": fcw_state, 
            "evp_state": evp_state, 
            "bsd_advisory": advisory,
            "skip_f": skip_f, "skip_r": skip_r, "skip_evp": skip_evp
        }
        metrics_dict = {"FCW": fcw_state, "EVP": evp_state, "Traffic": traffic_level}
        profiler.log_output(detections=log_data, annotated_frame=display_combined, extra_data=metrics_dict)
        profiler.frame_end()
        
        cv2.imshow("Unified Tri-Staggered Edge Pipeline", display_combined)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_f.release()
    cap_r.release()
    cv2.destroyAllWindows()
    siren_det.release()
    
    profiler.print_summary()
    profiler.export_csv("unified_profile.csv")
    print("[Unified] Pipeline stopped.")

if __name__ == "__main__":
    main()
