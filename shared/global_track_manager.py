import time
import numpy as np
from scipy.spatial.distance import cosine

class GlobalTrackManager:
    """
    Manages Re-Identification (Re-ID) across non-overlapping camera feeds.
    Temporarily caches feature embeddings of vehicles that exit one camera,
    and attempts to match them to new vehicles appearing in another camera.
    """
    def __init__(self, time_window=6.0, cosine_threshold=0.25):
        self.reid_cache = {}  # global_id -> {'features': array, 'timestamp': float}
        self.time_window = time_window
        self.cosine_threshold = cosine_threshold

    def register_exited_vehicle(self, global_id, features):
        if features is None:
            return
        self.reid_cache[global_id] = {
            'features': features,
            'timestamp': time.time()
        }

    def match_entered_vehicle(self, new_features):
        if new_features is None:
            return None
            
        current_time = time.time()
        best_match_id = None
        best_distance = float('inf')
        
        # Cleanup old cache entries
        self.reid_cache = {k: v for k, v in self.reid_cache.items() 
                           if current_time - v['timestamp'] <= self.time_window}

        for cached_id, data in self.reid_cache.items():
            dist = cosine(new_features, data['features'])
            if dist < self.cosine_threshold and dist < best_distance:
                best_distance = dist
                best_match_id = cached_id
                
        if best_match_id is not None:
            # Consume the cache so we don't match it again
            del self.reid_cache[best_match_id]
            return best_match_id
            
        return None
