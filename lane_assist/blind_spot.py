"""
blind_spot.py

Implements Blind Spot Detection (BSD) using Sliding Window Lane Detection
and 3D Cube Visualization.

Moved from fcw/blind_spot.py to lane_assist/blind_spot.py.
"""

import cv2
import numpy as np
from lane_assist import config


class BlindSpotAnalyzer:
    def __init__(self):
        self.prev_left = None
        self.prev_right = None
        self.left_fit_history = []
        self.right_fit_history = []
        self.last_cubes = None

        # Precompute Transform Matrix
        self.M = cv2.getPerspectiveTransform(config.BSD_ROI_SRC, config.BSD_ROI_DST)
        self.Minv = cv2.getPerspectiveTransform(config.BSD_ROI_DST, config.BSD_ROI_SRC)

    def analyze(self, frame):
        """
        Process frame for lane detection and return visualization + blind spot polygons.
        Returns:
            processed_frame: Frame with lane overlay
            blind_spots: List of polygons [(left_poly), (right_poly)]
            lane_info: dict with radius, offset, direction, road_type (or None)
        """
        frame_resized = cv2.resize(frame, (config.BSD_WIDTH, config.BSD_HEIGHT))

        # 1. Bird Eye View
        bird = cv2.warpPerspective(frame_resized, self.M,
                                   (config.BSD_WIDTH, config.BSD_HEIGHT))

        # 2. Thresholding (White + Yellow)
        hsv = cv2.cvtColor(bird, cv2.COLOR_BGR2HSV)

        lower_white = np.array([0, 0, 170])
        upper_white = np.array([180, 60, 255])
        lower_yellow = np.array([15, 80, 80])
        upper_yellow = np.array([35, 255, 255])

        mask_white = cv2.inRange(hsv, lower_white, upper_white)
        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        binary = cv2.bitwise_or(mask_white, mask_yellow)

        kernel = np.ones((5, 5), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 3. Sliding Window Search
        left_fit, right_fit = self._sliding_window(binary)

        # 4. Generate Lane & Cubes
        output_frame = frame_resized.copy()
        cubes = []

        if left_fit is not None and right_fit is not None:
            plot_y = np.linspace(0, config.BSD_HEIGHT - 1, config.BSD_HEIGHT)
            left_fit_x = left_fit[0] * plot_y**2 + left_fit[1] * plot_y + left_fit[2]
            right_fit_x = right_fit[0] * plot_y**2 + right_fit[1] * plot_y + right_fit[2]

            # Draw Lane overlay
            lane_overlay = np.zeros_like(bird)
            pts_left = np.array([np.transpose(np.vstack([left_fit_x, plot_y]))])
            pts_right = np.array([np.flipud(np.transpose(np.vstack([right_fit_x, plot_y])))])
            lane_pts = np.hstack((pts_left, pts_right)).astype(np.int32)
            cv2.fillPoly(lane_overlay, lane_pts, (0, 255, 0))

            final_overlay = cv2.warpPerspective(lane_overlay, self.Minv,
                                                (config.BSD_WIDTH, config.BSD_HEIGHT))
            output_frame = cv2.addWeighted(output_frame, 1, final_overlay, 0.4, 0)

            # 5. Generate 3D Cubes (Blind Spot Regions)
            left_cube_poly = self._get_cube_poly(left_fit_x, plot_y, is_left=True)
            right_cube_poly = self._get_cube_poly(right_fit_x, plot_y, is_left=False)

            # Smooth cubes to prevent rapid collapsing
            if self.last_cubes is not None:
                alpha = 0.15  # Heavy smoothing for coordinate points
                left_cube_poly = (alpha * left_cube_poly + (1.0 - alpha) * self.last_cubes[0]).astype(np.int32)
                right_cube_poly = (alpha * right_cube_poly + (1.0 - alpha) * self.last_cubes[1]).astype(np.int32)
                
            cubes = [left_cube_poly, right_cube_poly]
            self.last_cubes = cubes

            self._draw_cube(output_frame, left_cube_poly, (255, 140, 0))
            self._draw_cube(output_frame, right_cube_poly, (0, 140, 255))

            # 6. Curvature & Offset
            radius, offset, curve_param = self._measure_curvature_and_offset(
                left_fit, right_fit)

            if radius > 1500:
                road_type = "STRAIGHT"
            else:
                road_type = "CURVE RIGHT" if curve_param > 0 else "CURVE LEFT"

            lane_info = {
                "radius": radius,
                "offset": offset,
                "direction": "CENTER",
                "road_type": road_type
            }

            if offset > 0.1:
                lane_info["direction"] = "RIGHT"
            elif offset < -0.1:
                lane_info["direction"] = "LEFT"
        else:
            lane_info = None
            if self.last_cubes is not None:
                cubes = self.last_cubes
                self._draw_cube(output_frame, cubes[0], (255, 140, 0))
                self._draw_cube(output_frame, cubes[1], (0, 140, 255))

        return output_frame, cubes, lane_info

    def _measure_curvature_and_offset(self, left_fit, right_fit):
        """Calculates curvature radius and vehicle offset from center."""
        plot_y = np.linspace(0, config.BSD_HEIGHT - 1, config.BSD_HEIGHT)
        y_eval = np.max(plot_y)

        ym_per_pix = config.YM_PER_PIX
        xm_per_pix = config.XM_PER_PIX

        left_fit_x = left_fit[0] * plot_y**2 + left_fit[1] * plot_y + left_fit[2]
        right_fit_x = right_fit[0] * plot_y**2 + right_fit[1] * plot_y + right_fit[2]

        left_fit_cr = np.polyfit(plot_y * ym_per_pix, left_fit_x * xm_per_pix, 2)
        right_fit_cr = np.polyfit(plot_y * ym_per_pix, right_fit_x * xm_per_pix, 2)

        left_curverad = ((1 + (2 * left_fit_cr[0] * y_eval * ym_per_pix + left_fit_cr[1])**2)**1.5) / np.absolute(2 * left_fit_cr[0])
        right_curverad = ((1 + (2 * right_fit_cr[0] * y_eval * ym_per_pix + right_fit_cr[1])**2)**1.5) / np.absolute(2 * right_fit_cr[0])

        radius = (left_curverad + right_curverad) / 2

        lane_center_px = (left_fit_x[-1] + right_fit_x[-1]) / 2
        car_center_px = config.BSD_WIDTH / 2
        offset = (car_center_px - lane_center_px) * xm_per_pix

        return radius, offset, left_fit_cr[0]

    def _sliding_window(self, binary):
        histogram = np.sum(binary[binary.shape[0] // 2:, :], axis=0)
        midpoint = histogram.shape[0] // 2

        left_base = np.argmax(histogram[:midpoint])
        right_base = np.argmax(histogram[midpoint:]) + midpoint

        nonzero_y, nonzero_x = binary.nonzero()

        current_left_x = left_base
        current_right_x = right_base

        left_x, left_y = [], []
        right_x, right_y = [], []

        for y in range(config.BSD_HEIGHT, 0, -config.BSD_WINDOW_HEIGHT):
            win_y_low = y - config.BSD_WINDOW_HEIGHT
            win_y_high = y

            lx_low = max(0, current_left_x - config.BSD_WINDOW_HALF_WIDTH)
            lx_high = min(config.BSD_WIDTH, current_left_x + config.BSD_WINDOW_HALF_WIDTH)
            rx_low = max(0, current_right_x - config.BSD_WINDOW_HALF_WIDTH)
            rx_high = min(config.BSD_WIDTH, current_right_x + config.BSD_WINDOW_HALF_WIDTH)

            left_inds = ((nonzero_y >= win_y_low) & (nonzero_y < win_y_high) &
                         (nonzero_x >= lx_low) & (nonzero_x < lx_high))
            right_inds = ((nonzero_y >= win_y_low) & (nonzero_y < win_y_high) &
                          (nonzero_x >= rx_low) & (nonzero_x < rx_high))

            lx = nonzero_x[left_inds]
            ly = nonzero_y[left_inds]
            rx = nonzero_x[right_inds]
            ry = nonzero_y[right_inds]

            if len(lx) > config.BSD_MIN_PIXELS:
                current_left_x = int(np.mean(lx))
            if len(rx) > config.BSD_MIN_PIXELS:
                current_right_x = int(np.mean(rx))

            left_x.extend(lx)
            left_y.extend(ly)
            right_x.extend(rx)
            right_y.extend(ry)

        if len(left_x) < 50 or len(right_x) < 50:
            if self.prev_left and self.prev_right:
                left_x, left_y = self.prev_left
                right_x, right_y = self.prev_right
            else:
                return None, None

        self.prev_left = (left_x, left_y)
        self.prev_right = (right_x, right_y)

        left_fit = np.polyfit(left_y, left_x, 2)
        right_fit = np.polyfit(right_y, right_x, 2)

        self.left_fit_history.append(left_fit)
        self.right_fit_history.append(right_fit)

        if len(self.left_fit_history) > config.BSD_MAX_HISTORY:
            self.left_fit_history.pop(0)
        if len(self.right_fit_history) > config.BSD_MAX_HISTORY:
            self.right_fit_history.pop(0)

        left_fit_avg = np.mean(self.left_fit_history, axis=0)
        right_fit_avg = np.mean(self.right_fit_history, axis=0)

        return left_fit_avg, right_fit_avg

    def _get_cube_poly(self, fit_x, plot_y, is_left):
        y_bottom = config.BSD_HEIGHT - 1
        y_top = int(config.BSD_HEIGHT * 0.45)

        x_bottom = int(fit_x[y_bottom])
        x_top = int(fit_x[y_top])

        cube_width = 140

        if is_left:
            pts = np.array([
                [x_bottom - cube_width, y_bottom],
                [x_bottom, y_bottom],
                [x_top, y_top],
                [x_top - cube_width, y_top]
            ], dtype=np.float32)
        else:
            pts = np.array([
                [x_bottom, y_bottom],
                [x_bottom + cube_width, y_bottom],
                [x_top + cube_width, y_top],
                [x_top, y_top]
            ], dtype=np.float32)

        poly_orig = cv2.perspectiveTransform(
            pts.reshape(-1, 1, 2), self.Minv
        ).reshape(-1, 2).astype(np.int32)
        return poly_orig

    def _draw_cube(self, image, base_pts, color):
        height = int(0.3 * config.BSD_HEIGHT)
        base = np.array(base_pts, dtype=np.int32)
        top = base.copy()
        top[:, 1] -= height

        cv2.polylines(image, [base], True, color, 2)
        cv2.polylines(image, [top], True, color, 2)
        for i in range(4):
            cv2.line(image, tuple(base[i]), tuple(top[i]), color, 2)
