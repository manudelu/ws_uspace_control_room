#!/usr/bin/env python3

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi
from typing import Dict, Any

class LowPassFilter:
    """Manages low-pass filtering for multiple signals across multiple drones."""

    def __init__(self, cutoff: float, fs: float, order: int):
        """
        Initialize the filter.
        :param cutoff: Cutoff frequency in Hz
        :param fs: Sampling frequency in Hz
        :param order: Filter order
        """
        self.cutoff = cutoff
        self.fs = fs
        self.order = order
        self.lpf_state: Dict[str, Dict[str, Any]] = {}  # Stores filter states per drone & field

        # Compute filter coefficients
        self.b, self.a = self.butter_lowpass()

    def butter_lowpass(self):
        """Create a Butterworth low-pass filter."""
        nyquist = 0.5 * self.fs
        normal_cutoff = self.cutoff / nyquist
        return butter(self.order, normal_cutoff, btype='low', analog=False)

    def apply(self, data: float, drone_id: str, field: str) -> float:
        """
        Apply the low-pass filter to a given data point.
        :param data: New data sample
        :param drone_id: The drone's ID
        :param field: The specific field being filtered (e.g., "latitude", "yaw")
        :return: Filtered data sample
        """
        if drone_id not in self.lpf_state:
            self.lpf_state[drone_id] = {}

        if field not in self.lpf_state[drone_id]:
            zi = lfilter_zi(self.b, self.a) * data  # Initialize filter state
            self.lpf_state[drone_id][field] = {'z': zi}

        # Apply filter
        filtered_data, z = lfilter(self.b, self.a, [data], zi=self.lpf_state[drone_id][field]['z'])
        self.lpf_state[drone_id][field]['z'] = z  # Update filter state
        return filtered_data[0]