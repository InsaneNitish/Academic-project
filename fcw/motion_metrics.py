"""
motion_metrics.py

Computes motion metrics for FCW logic.
(A) Bounding Box Area Growth
(B) Vertical Expansion Rate
(C) Temporal Smoothing
"""

import numpy as np
from typing import Deque, Tuple
from fcw import config

def calculate_box_area(bbox: Tuple[float, float, float, float]) -> float:
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w * h

def get_bottom_y(bbox: Tuple[float, float, float, float]) -> float:
    return bbox[3]

def compute_growth_rate(history: Deque[Tuple[float, float, float, float]]) -> float:
    """
    Computes smoothed area growth rate.
    Growth = (Area_t - Area_t-1) / Area_t-1
    Returns smoothed value over track history (last 5 frames approx via EMA or average).
    Using EMA as per prompt "Exponential smoothing".
    """
    if len(history) < 2:
        return 0.0
    
    # Calculate raw growth rates for recent frames
    growth_rates = []
    
    # Convert deque to list for indexing
    hist_list = list(history)
    
    # Iterate backwards from newest
    for i in range(len(hist_list) - 1, 0, -1):
        curr_box = hist_list[i]
        prev_box = hist_list[i-1]
        
        curr_area = calculate_box_area(curr_box)
        prev_area = calculate_box_area(prev_box)
        
        if prev_area <= 0:
            rate = 0.0
        else:
            rate = (curr_area - prev_area) / prev_area
            
        growth_rates.append(rate)
        
        # Limit lookback for smoothing if needed, but history is already short (10)
        # Prompt says "Temporal Smoothing Apply exponential smoothing over last 5 frames"
        if len(growth_rates) >= 5:
            break
            
    # Apply EMA
    # Reverse back to chronological order for EMA: [oldest_rate, ..., newest_rate]
    growth_rates.reverse()
    
    if not growth_rates:
        return 0.0

    ema = growth_rates[0]
    alpha = config.SMOOTHING_ALPHA
    
    for r in growth_rates[1:]:
        ema = alpha * r + (1 - alpha) * ema
        
    return ema

def compute_vertical_expansion_rate(history: Deque[Tuple[float, float, float, float]]) -> float:
    """
    Computes smoothed vertical expansion rate (pixels/frame).
    Expansion = y_bottom_t - y_bottom_t-1
    """
    if len(history) < 2:
        return 0.0
        
    velocities = []
    hist_list = list(history)
    
    # Iterate backwards
    for i in range(len(hist_list) - 1, 0, -1):
        curr_y = get_bottom_y(hist_list[i])
        prev_y = get_bottom_y(hist_list[i-1])
        
        vel = curr_y - prev_y
        velocities.append(vel)
        
        if len(velocities) >= 5:
            break
            
    velocities.reverse()
    
    if not velocities:
        return 0.0
        
    ema = velocities[0]
    alpha = config.SMOOTHING_ALPHA
    
    for v in velocities[1:]:
        ema = alpha * v + (1 - alpha) * ema
        
    return ema
