"""
ego_path.py

Defines the ego vehicle's projected path and checks for object overlap.
Constraint: Static path definition (Center 40%, Bottom 60%).
"""

import numpy as np
from typing import Tuple, List, Dict
from fcw import config

def get_ego_region(frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
    """
    Returns the ego path region (x1, y1, x2, y2).
    Center 40% width, Bottom 60% height.
    """
    center_x = frame_width // 2
    path_width = int(frame_width * config.EGO_WIDTH_PCT)
    path_height = int(frame_height * config.EGO_HEIGHT_PCT)
    
    x1 = center_x - (path_width // 2)
    x2 = center_x + (path_width // 2)
    y1 = frame_height - path_height
    y2 = frame_height
    
    return (x1, y1, x2, y2)

def compute_overlap_x(bbox: Tuple[float, float, float, float], ego_x_range: Tuple[int, int]) -> float:
    """
    Computes horizontal overlap ratio between bbox and ego path.
    bbox: (x1, y1, x2, y2)
    ego_x_range: (ego_x1, ego_x2)
    
    Returns: Overlap ratio (0.0 to 1.0) relative to bbox width.
    """
    box_x1, _, box_x2, _ = bbox
    ego_x1, ego_x2 = ego_x_range
    
    # Intersection X
    inter_x1 = max(box_x1, ego_x1)
    inter_x2 = min(box_x2, ego_x2)
    
    if inter_x2 <= inter_x1:
        return 0.0
        
    intersection_width = inter_x2 - inter_x1
    box_width = box_x2 - box_x1
    
    if box_width <= 0:
        return 0.0
        
    return intersection_width / box_width

def is_in_ego_path(bbox: Tuple[float, float, float, float], frame_width: int, frame_height: int) -> bool:
    """
    Determines if a bounding box is in the ego path.
    Criteria: >= 30% horizontal overlap with ego path region.
    """
    ego_rect = get_ego_region(frame_width, frame_height)
    ego_x_range = (ego_rect[0], ego_rect[2])
    
    overlap = compute_overlap_x(bbox, ego_x_range)
    
    # Also check if object is vertically relevant (within the ego vertical zone or below it? 
    # Usually ego path extends from bottom to horizon. 
    # The prompt says "Bottom 60% height of image". 
    # We should strictly adhere to "in ego path if >= 30% horizontal overlap with ego path region".
    # But usually objects above the path (sky) shouldn't count, but cars are usually on road.
    # We will strictly check geometric overlap with the defined box for now, 
    # but considering perspective, distant cars might be above the line?
    # Prompt: "Define ego path as: Center 40% width... Bottom 60% height... Object considered in path if >=30% horizontal overlap WITH EGO PATH REGION"
    # This implies the object must overlap the region defined (x,y space). So if it's way above, it's not "in" the region.
    
    box_y2 = bbox[3] # Bottom of box
    ego_y1 = ego_rect[1] # Top of ego region
    
    # Check vertical overlap as well? The criteria 'overlap with ego path region' usually implies 2D intersection or X-overlap within Y-bounds.
    # Given "horizontal overlap", let's assume if it aligns horizontally it's a threat, 
    # BUT the "Bottom 60%" constraint defines the region.
    # If a car is strictly above the bottom 60% (far away), is it in ego path? 
    # "An object is considered in ego path if >= 30% horizontal overlap with ego path region"
    # This phrasing is slightly ambiguous: does it mean overlap with the infinite vertical strip defined by ego path width, 
    # or overlap with the specific rectangle?
    # "Ego path as: Center 40% width, Bottom 60% height". This defines a Rectangle.
    # "Overlap with ego path region" -> Intersection Area / Box Area? No, "horizontal overlap".
    # I will interpret this as: The object must be spatially interacting with that rectangle. 
    # If the object is fully above the rectangle, it technically doesn't overlap the "region".
    # However, cars at long range might be above the bottom 60%. 
    # But for FCW, we care about 'deteriorating' scenes, usually closer. 
    # I will stick to the rectangle intersection logic: Check if Y ranges also overlap? 
    # Use standard 2D intersection? 
    # ">=30% horizontal overlap" is the specific metric. 
    # I will enforce that the object must vertically overlap the region as well to be "in" it, 
    # otherwise we detect birds or bridges.
    
    ego_y2 = ego_rect[3]
    box_y1 = bbox[1]
    
    # Vertical intersection
    inter_y1 = max(box_y1, ego_y1)
    inter_y2 = min(box_y2, ego_y2)
    
    if inter_y2 <= inter_y1:
        return False # No vertical overlap
        
    return overlap >= config.EGO_OVERLAP_THRESH


def get_ego_polygon(frame_width: int, frame_height: int) -> np.ndarray:
    """
    Returns the ego path region as a polygon (4 vertices) for visualization.
    Trapezoidal shape: narrower at top (perspective), wider at bottom.
    """
    ego_rect = get_ego_region(frame_width, frame_height)
    ex1, ey1, ex2, ey2 = ego_rect

    # Narrow the top edge to approximate perspective
    center_x = frame_width // 2
    top_half_w = int((ex2 - ex1) * 0.35)

    return np.array([
        [ex1, ey2],                         # Bottom-left
        [center_x - top_half_w, ey1],       # Top-left (narrower)
        [center_x + top_half_w, ey1],       # Top-right (narrower)
        [ex2, ey2],                         # Bottom-right
    ], dtype=np.int32)
