"""
ui_renderer.py

Modern HUD-style overlay renderer for ADAS video output.
Provides consistent, premium visual elements across all modules.

Color Scheme:
    SAFE    = Green  (#00E676)
    WARNING = Amber  (#FFB300)
    DANGER  = Red    (#FF1744)
    INFO    = Blue   (#29B6F6)
"""

import cv2
import numpy as np
from shared import config_common as cfg


class UIRenderer:
    """Draws modern, semi-transparent HUD elements on video frames."""

    # Severity levels
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    INFO = "INFO"

    _COLORS = {
        "SAFE": cfg.COLOR_SAFE,
        "WARNING": cfg.COLOR_WARNING,
        "DANGER": cfg.COLOR_DANGER,
        "INFO": cfg.COLOR_INFO,
    }

    def __init__(self, module_name: str = "ADAS"):
        self.module_name = module_name

    # ------------------------------------------------------------------
    # Core drawing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _overlay(frame, overlay, alpha=0.7):
        """Blend overlay onto frame with transparency."""
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    @staticmethod
    def _rounded_rect(img, pt1, pt2, color, radius=12, thickness=-1):
        """Draw a rounded rectangle (filled or outline)."""
        x1, y1 = pt1
        x2, y2 = pt2
        r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)

        # Use overlay for anti-aliasing
        if thickness == -1:
            # Top and bottom bars
            cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1)
            # Left and right bars
            cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1)
            # Corners
            cv2.circle(img, (x1 + r, y1 + r), r, color, -1)
            cv2.circle(img, (x2 - r, y1 + r), r, color, -1)
            cv2.circle(img, (x1 + r, y2 - r), r, color, -1)
            cv2.circle(img, (x2 - r, y2 - r), r, color, -1)
        else:
            # Outline only
            cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness)
            cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness)
            cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness)
            cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness)
            cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
            cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
            cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
            cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)

    def _get_color(self, severity: str):
        return self._COLORS.get(severity, cfg.COLOR_INFO)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw_module_badge(self, frame, y_pos=8):
        """Draw module name badge."""
        overlay = frame.copy()
        h, w = frame.shape[:2]
        badge_w = max(160, len(self.module_name) * 14 + 30)
        self._rounded_rect(overlay, (10, y_pos), (10 + badge_w, y_pos + 32), cfg.COLOR_BG_DARK, radius=8)
        self._overlay(frame, overlay, alpha=0.7)

        # Accent line
        cv2.line(frame, (14, y_pos + 4), (14, y_pos + 28), cfg.COLOR_INFO, 3)
        cv2.putText(frame, self.module_name, (22, y_pos + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, cfg.COLOR_WHITE, 1, cv2.LINE_AA)

    def draw_fps(self, frame, fps: float):
        """Draw FPS counter at bottom-right."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        self._rounded_rect(overlay, (w - 110, h - 35), (w - 10, h - 8), cfg.COLOR_BG_DARK, radius=6)
        self._overlay(frame, overlay, alpha=0.7)

        color = cfg.COLOR_SAFE if fps >= 15 else (cfg.COLOR_WARNING if fps >= 8 else cfg.COLOR_DANGER)
        cv2.putText(frame, f"{fps:.0f} FPS", (w - 100, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

    def draw_status_panel(self, frame, x, y, width, lines: list, severity="INFO"):
        """
        Draw a status panel with colored accent and text lines.
        Args:
            lines: List of (label, value) tuples or plain strings.
        """
        line_h = 24
        panel_h = max(50, len(lines) * line_h + 20)
        accent_color = self._get_color(severity)

        overlay = frame.copy()
        self._rounded_rect(overlay, (x, y), (x + width, y + panel_h), cfg.COLOR_BG_DARK, radius=8)
        self._overlay(frame, overlay, alpha=0.65)

        # Accent bar on left
        cv2.rectangle(frame, (x, y + 6), (x + 4, y + panel_h - 6), accent_color, -1)

        # Text lines
        ty = y + 22
        for line in lines:
            if isinstance(line, tuple):
                label, value = line
                cv2.putText(frame, f"{label}:", (x + 12, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, cfg.COLOR_TEXT_DIM, 1, cv2.LINE_AA)
                cv2.putText(frame, str(value), (x + 12 + len(label) * 9 + 8, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, cfg.COLOR_WHITE, 1, cv2.LINE_AA)
            else:
                cv2.putText(frame, str(line), (x + 12, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, cfg.COLOR_WHITE, 1, cv2.LINE_AA)
            ty += line_h

    def draw_alert_banner(self, frame, text: str, severity="DANGER"):
        """Draw a full-width gradient alert banner at the top."""
        h, w = frame.shape[:2]
        banner_h = 50
        color = self._get_color(severity)

        # Create gradient banner
        overlay = frame.copy()
        for i in range(banner_h):
            alpha_row = 0.8 - (i / banner_h) * 0.5
            cv2.line(overlay, (0, i), (w, i), color, 1)

        self._overlay(frame, overlay, alpha=0.5)

        # Text centered
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        tx = (w - text_size[0]) // 2
        cv2.putText(frame, text, (tx, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, cfg.COLOR_WHITE, 2, cv2.LINE_AA)

    def draw_bbox(self, frame, x1, y1, x2, y2, label="", severity="INFO",
                  show_glow=False):
        """Draw a styled bounding box with optional glow effect."""
        color = self._get_color(severity)
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

        if severity == "INFO":
            # Very thin, subtle box for background traffic
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
        else:
            if show_glow:
                # Outer glow
                cv2.rectangle(frame, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), color, 3)
    
            # Main box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    
            # Corner accents
            corner_len = min(15, (x2 - x1) // 4, (y2 - y1) // 4)
            thick = 3
            # Top-left
            cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, thick)
            cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, thick)
            # Top-right
            cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, thick)
            cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, thick)
            # Bottom-left
            cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, thick)
            cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, thick)
            # Bottom-right
            cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, thick)
            cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, thick)

        # Label tag
        if label:
            tag_w = len(label) * 9 + 10
            tag_h = 20
            overlay = frame.copy()
            cv2.rectangle(overlay, (x1, y1 - tag_h), (x1 + tag_w, y1), color, -1)
            self._overlay(frame, overlay, alpha=0.8)
            cv2.putText(frame, label, (x1 + 4, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, cfg.COLOR_WHITE, 1, cv2.LINE_AA)

    def draw_metric_bar(self, frame, x, y, width, value, max_value,
                        label="", severity="INFO"):
        """Draw a horizontal progress/metric bar."""
        bar_h = 14
        color = self._get_color(severity)

        # Background
        overlay = frame.copy()
        self._rounded_rect(overlay, (x, y), (x + width, y + bar_h), (50, 50, 50), radius=4)
        self._overlay(frame, overlay, alpha=0.5)

        # Fill
        fill_w = int((min(value, max_value) / max(max_value, 0.001)) * (width - 4))
        if fill_w > 2:
            cv2.rectangle(frame, (x + 2, y + 2), (x + 2 + fill_w, y + bar_h - 2), color, -1)

        # Label
        if label:
            cv2.putText(frame, label, (x, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, cfg.COLOR_TEXT_DIM, 1, cv2.LINE_AA)

    def draw_lane_overlay(self, frame, mask=None, poly=None,
                          color=(0, 255, 0), alpha=0.3):
        """Draw drivable area overlay from mask or polygon."""
        if mask is not None:
            color_mask = np.zeros_like(frame)
            color_mask[:, :, 1] = mask  # Green channel
            cv2.addWeighted(frame, 1.0, color_mask, alpha, 0, frame)
        elif poly is not None:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [np.array(poly, dtype=np.int32)], color)
            cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    def draw_roi(self, frame, points, color=None):
        """Draw ROI polygon outline."""
        color = color or cfg.COLOR_INFO
        pts = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [pts], True, color, 1, cv2.LINE_AA)

    def compose_dashboard(self, frame, fps, severity, metrics: dict, bottom_badge=False):
        """
        Convenience method: draws badge + FPS + status panel from metrics dict.
        Args:
            metrics: dict of {"label": value} pairs to display in the panel.
            bottom_badge: If True, draws badge directly above the panel instead of top-left.
        """
        self.draw_fps(frame, fps)

        lines = [(k, v) for k, v in metrics.items()]
        h = frame.shape[0]
        
        # Calculate dynamic height to anchor it to the bottom
        panel_h = max(50, len(lines) * 24 + 20)
        y_pos = h - panel_h - 15  # 15px margin from bottom

        if bottom_badge:
            self.draw_module_badge(frame, y_pos=y_pos - 36)
        else:
            self.draw_module_badge(frame, y_pos=8)
            
        self.draw_status_panel(frame, 10, y_pos, 240, lines, severity=severity)
