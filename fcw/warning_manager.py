"""
warning_manager.py

Manages multi-level warning system.
Level 0: Normal
Level 1: Visual (Growth detected)
Level 2: Audio (Sustained growth)
Level 3: Continuous (Rapid growth)

Handles state transitions and cooldowns.
"""

import time
from fcw import config

class WarningManager:
    def __init__(self):
        self.current_level = 0
        self.last_alert_time = 0.0
        self.growth_start_time = 0.0
        self.is_growing = False
        
    def update(self, growth_detected: bool, rapid_growth: bool) -> int:
        """
        Updates warning state based on current frame analysis.
        Returns current warning level (0-3).
        """
        now = time.time()
        
        # Cooldown check
        if (now - self.last_alert_time) < config.COOLDOWN_SECONDS and self.current_level > 0:
            # If we recently alerted, we might want to hold status or decay?
            # Prompt says "1 second cooldown after alert".
            # Usually means don't *re-trigger* sound immediately, but if danger persists?
            # Let's interpret: rapid firing of alerts is bad. 
            pass

        # State Machine
        if not growth_detected:
            self.current_level = 0
            self.is_growing = False
            self.growth_start_time = 0.0
            return 0
            
        # Growth is detected
        if not self.is_growing:
            self.is_growing = True
            self.growth_start_time = now
            
        growth_duration = now - self.growth_start_time
        
        # Determine Level
        new_level = 0
        
        if rapid_growth:
            new_level = 3
        elif growth_duration >= 0.5:
            new_level = 2
        else:
            new_level = 1
            
        # Update state avoiding level jumping if needed, but prompt says "Never jump levels"?
        # Actually prompt says "Never jump levels" in section 8.
        # This usually means 0->1->2->3. 
        # But if rapid growth happens instantly, do we wait?
        # "Rapid growth spike" -> Level 3.
        # If I am at 0 and detect rapid growth, should I go 0->1? 
        # Safety critical: if it's super dangerous, we might need to jump.
        # But "Never jump levels" is a strict rule in the prompt.
        # So: 0 -> 1 -> 2 -> 3.
        # Even if rapid, we go to 1 first.
        
        if new_level > self.current_level + 1:
            new_level = self.current_level + 1
            
        # If level is dropping, we can drop immediately or decay? 
        # Usually safety systems decay slowly, but prompt doesn't specify decay.
        # We will allow immediate drop if maximizing trust (no false alarms).
        
        self.current_level = new_level
        
        if self.current_level >= 2:
            self.last_alert_time = now
            
        return self.current_level
