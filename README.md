# ADAS Modular System for Indian Roads

A modular Advanced Driver Assistance System optimized for Indian traffic conditions.
Each module runs **independently** for development and testing, and can be integrated later.

## Modules

### 1. FCW – Forward Collision Warning
Camera-only collision warning using YOLOv8n and motion-based risk assessment.
```bash
python -m fcw.main --source videos/new1.mp4
```

### 2. Lane Assist + Blind Spot Detection
Lane boundary analysis with blind spot detection for lane change safety.
```bash
python -m lane_assist.main --source videos/new.mp4
```

### 3. Emergency Vehicle Preemption (EVP)
Detects emergency vehicles via flashing lights and optional siren audio.
```bash
python -m emergency_preemption.main --source videos/video_demo.mp4
python -m emergency_preemption.main --source 0 --microphone  # With audio
```

## Project Structure

```
indian_fcw/
├── shared/                    # Shared utilities (detector, tracker, UI, profiler)
├── fcw/                       # Forward Collision Warning module
├── lane_assist/               # Lane Assist + Blind Spot Detection module
├── emergency_preemption/      # Emergency Vehicle Preemption module
├── videos/                    # Test videos
├── requirements.txt
└── README.md
```

## Installation

```bash
pip install -r requirements.txt
```

## Requirements
- Python 3.10+
- GPU recommended (runs on CPU with YOLOv8n)

## Resource Profiling
Each module prints a resource summary on exit and exports a `*_profile.csv` with per-frame metrics (FPS, data rate, bandwidth, storage estimates).

## UI/UX
All modules use a modern HUD-style overlay with:
- **Green** indicators for safe conditions
- **Amber** indicators for warnings
- **Red** indicators for critical alerts
- Semi-transparent panels, corner-accent bounding boxes, and gradient alert banners
