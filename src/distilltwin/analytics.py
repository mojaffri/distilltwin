"""Dependency-light residual monitoring used by the fault experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EWMAResidualMonitor:
    """Online residual monitor for sensor-bias and model-mismatch alarms."""

    smoothing: float = 0.15
    alarm_threshold: float = 0.025
    value: float = 0.0
    initialized: bool = False

    def __post_init__(self) -> None:
        if not np.isfinite(self.smoothing) or not 0.0 < self.smoothing <= 1.0:
            raise ValueError("smoothing must be finite and in (0, 1]")
        if not np.isfinite(self.alarm_threshold) or self.alarm_threshold <= 0.0:
            raise ValueError("alarm_threshold must be finite and positive")

    def update(self, residual: float) -> tuple[float, bool]:
        if not np.isfinite(residual):
            raise ValueError("residual must be finite")
        self.value = (
            float(residual)
            if not self.initialized
            else self.smoothing * float(residual) + (1.0 - self.smoothing) * self.value
        )
        self.initialized = True
        return self.value, abs(self.value) >= self.alarm_threshold
