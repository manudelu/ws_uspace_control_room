#!/usr/bin/env python3

import math
import numpy as np
from typing import Dict, Tuple

def normalize_angle(angle: float) -> float:
    """Normalize angle to [-180, 180] range, ensuring 180 stays 180."""
    normalized = (angle + 180) % 360 - 180
    return normalized if not (normalized == -180 and angle > 0) else 180


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min_val and max_val."""
    return max(min_val, min(max_val, value))


class PIDController:
    def __init__(self,
                 kp_vert: float, kd_vert: float, ki_vert: float,
                 kp_horiz: float, kd_horiz: float, ki_horiz: float,
                 kp_yaw: float, kd_yaw: float, ki_yaw: float,
                 integral_limit: float, alpha: float,
                 output_limit: float):
        """
        PID Controller for drone navigation.

        Args:
            kp_*, ki_*, kd_*: PID gains for vertical, horizontal, and yaw axes.
            integral_limit: Maximum magnitude of accumulated integral error.
            alpha: Filter factor for derivative smoothing [0..1].
            output_limit: Maximum magnitude of velocity adjustment.
        """
        self.kp_vert, self.kd_vert, self.ki_vert = kp_vert, kd_vert, ki_vert
        self.kp_horiz, self.kd_horiz, self.ki_horiz = kp_horiz, kd_horiz, ki_horiz
        self.kp_yaw, self.kd_yaw, self.ki_yaw = kp_yaw, kd_yaw, ki_yaw

        self.integral_limit = integral_limit
        self.alpha = alpha
        self.output_limit = output_limit

        # Error tracking
        self.p_error: Dict[str, float] = {k: 0.0 for k in ['lat', 'lon', 'alt', 'yaw']}
        self.prev_p_error: Dict[str, float] = {k: 0.0 for k in ['lat', 'lon', 'alt', 'yaw']}
        self.d_error: Dict[str, float] = {k: 0.0 for k in ['lat', 'lon', 'alt', 'yaw']}
        self.i_error: Dict[str, float] = {k: 0.0 for k in ['lat', 'lon', 'alt', 'yaw']}

    def reset_integral(self):
        """Reset accumulated integral error (useful when switching modes)."""
        for key in self.i_error:
            self.i_error[key] = 0.0

    def compute(self,
                latitude: float,
                longitude: float,
                altitude: float,
                yaw: float,
                sim_lat: float,
                sim_lon: float,
                sim_alt: float,
                sim_yaw: float,
                dt: float) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
        """
        Compute velocity adjustments using PID control.

        Returns:
            Tuple containing:
              - velocity_adjustment dict with x, y, z, yaw corrections
              - debug dict with P, I, D contributions and raw errors
        """
        lat_to_meters = 111_139.0
        lon_to_meters_real = 111_139.0 * math.cos(math.radians(latitude))
        lon_to_meters_sim = 111_139.0 * math.cos(math.radians(sim_lat))

        # Errors
        self.p_error['lat'] = (latitude - sim_lat) * lat_to_meters
        self.p_error['lon'] = (longitude - sim_lon) * ((lon_to_meters_real + lon_to_meters_sim) / 2)
        self.p_error['alt'] = altitude - sim_alt
        self.p_error['yaw'] = normalize_angle(yaw - sim_yaw)

        # Derivative (filtered)
        for key in self.p_error:
            raw_derivative = (self.p_error[key] - self.prev_p_error[key]) / dt
            self.d_error[key] = self.alpha * raw_derivative + (1 - self.alpha) * self.d_error[key]

        # Integral with windup guard
        for key in self.p_error:
            self.i_error[key] += self.p_error[key] * dt
            self.i_error[key] = clamp(self.i_error[key], -self.integral_limit, self.integral_limit)

        # Adaptive gains based on error magnitude
        velocity_magnitude = np.linalg.norm([
            self.p_error['lat'],
            self.p_error['lon'],
            self.p_error['alt']
        ])
        gain_factor = min(1.0, velocity_magnitude / 2.0)

        kp_horiz, ki_horiz, kd_horiz = self.kp_horiz * gain_factor, self.ki_horiz * gain_factor, self.kd_horiz
        kp_vert, ki_vert, kd_vert = self.kp_vert * gain_factor, self.ki_vert * gain_factor, self.kd_vert

        # Contributions
        p_terms = {
            'x': kp_horiz * self.p_error['lat'],
            'y': kp_horiz * self.p_error['lon'],
            'z': kp_vert * self.p_error['alt'],
            'yaw': self.kp_yaw * self.p_error['yaw'],
        }
        i_terms = {
            'x': ki_horiz * self.i_error['lat'],
            'y': ki_horiz * self.i_error['lon'],
            'z': ki_vert * self.i_error['alt'],
            'yaw': self.ki_yaw * self.i_error['yaw'],
        }
        d_terms = {
            'x': kd_horiz * self.d_error['lat'],
            'y': kd_horiz * self.d_error['lon'],
            'z': kd_vert * self.d_error['alt'],
            'yaw': self.kd_yaw * self.d_error['yaw'],
        }

        # Compute outputs with clamping
        velocity_adjustment = {
            axis: clamp(p_terms[axis] + i_terms[axis] + d_terms[axis], -self.output_limit, self.output_limit)
            for axis in ['x', 'y', 'z', 'yaw']
        }

        # Update state
        self.prev_p_error = self.p_error.copy()

        debug_info = {
            'p': p_terms,
            'i': i_terms,
            'd': d_terms,
            'error': self.p_error.copy()
        }

        return velocity_adjustment, debug_info