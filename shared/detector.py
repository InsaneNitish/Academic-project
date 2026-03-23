"""
detector.py

Wraps YOLOv8n for object detection.
Optimized with FP16, TensorRT support, and optional ROI cropping.
Shared across all ADAS modules.
"""

from ultralytics import YOLO
import numpy as np
import torch
from typing import List, Tuple, Optional
from shared import config_common as cfg


class Detector:
    def __init__(self, model_path: str = None, confidence: float = None):
        """
        Initialize YOLOv8 detector with optimizations.
        
        Supports .pt (PyTorch) and .engine (TensorRT) model formats.
        TensorRT models run 2-3x faster on NVIDIA GPUs.
        
        To export TensorRT model:
            yolo export model=yolov8n.pt format=engine half=True device=0
        """
        model_path = model_path or cfg.MODEL_PATH
        confidence = confidence or cfg.CONFIDENCE_THRESHOLD

        # Determine target classes and names dynamically based on model
        if model_path != cfg.MODEL_PATH:
            temp_model = YOLO(model_path)
            self.class_names = temp_model.names
            self.target_classes = list(self.class_names.keys())
            del temp_model
        else:
            self.class_names = cfg.CLASS_NAMES
            self.target_classes = cfg.TARGET_CLASSES

        # Determine device
        self.device = 'cpu'
        self.use_half = False
        if cfg.USE_GPU and torch.cuda.is_available():
            self.device = 0
            self.use_half = True  # FP16 on GPU
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[Detector] GPU: {gpu_name} | FP16: ON")
        else:
            print("[Detector] Using CPU | FP16: OFF")

        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.confidence = confidence
        
        # Warm up the model (first inference is slow)
        self._warmup()

    def _warmup(self):
        """Run a dummy inference to warm up the model."""
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        try:
            self.model.predict(dummy, conf=0.5, verbose=False,
                               half=self.use_half)
            print("[Detector] Warmup complete.")
        except Exception:
            pass

    def detect(self, frame_bgr: np.ndarray,
               target_classes: List[int] = None,
               crop_region: Optional[Tuple[int, int, int, int]] = None
               ) -> Tuple[List, List, List]:
        """
        Run inference on a single frame.
        
        Args:
            frame_bgr: Input frame (BGR)
            target_classes: COCO class IDs to detect
            crop_region: Optional (x1, y1, x2, y2) to crop before detection.
                         Detections are mapped back to original coordinates.
        
        Returns:
            detections_xyxy: List of [x1, y1, x2, y2]
            detections_confidence: List of float
            detections_class_id: List of int
        """
        target_classes = target_classes if target_classes is not None else self.target_classes

        # Crop optimization: detect only in ROI
        offset_x, offset_y = 0, 0
        detect_frame = frame_bgr
        
        if crop_region is not None:
            cx1, cy1, cx2, cy2 = crop_region
            detect_frame = frame_bgr[cy1:cy2, cx1:cx2]
            offset_x, offset_y = cx1, cy1

        results = self.model.predict(
            detect_frame,
            conf=self.confidence,
            classes=target_classes,
            verbose=False,
            half=self.use_half  # FP16 optimization
        )

        detections_xyxy = []
        detections_confidence = []
        detections_class_id = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())

                if cls_id in self.class_names:
                    # Map back to original coordinates if cropped
                    detections_xyxy.append([
                        float(x1) + offset_x,
                        float(y1) + offset_y,
                        float(x2) + offset_x,
                        float(y2) + offset_y
                    ])
                    detections_confidence.append(conf)
                    detections_class_id.append(cls_id)

        return detections_xyxy, detections_confidence, detections_class_id
