"""Small, dependency-light analytics used by the digital-twin experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass
class RidgeSoftSensor:
    """Standardized ridge regression for estimating composition from process signals."""

    regularization: float = 1e-3
    feature_mean: FloatArray | None = None
    feature_scale: FloatArray | None = None
    coefficients: FloatArray | None = None
    intercept: float | None = None

    def fit(self, features: FloatArray, target: FloatArray) -> RidgeSoftSensor:
        x = np.asarray(features, dtype=float)
        y = np.asarray(target, dtype=float)
        if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
            raise ValueError("features must be 2D and aligned with a 1D target")
        self.feature_mean = x.mean(axis=0)
        scale = x.std(axis=0)
        self.feature_scale = np.where(scale < 1e-12, 1.0, scale)
        standardized = (x - self.feature_mean) / self.feature_scale
        design = np.column_stack([np.ones(len(x)), standardized])
        penalty = np.eye(design.shape[1]) * self.regularization
        penalty[0, 0] = 0.0
        solution = np.linalg.solve(design.T @ design + penalty, design.T @ y)
        self.intercept = float(solution[0])
        self.coefficients = solution[1:].astype(np.float64)
        return self

    def predict(self, features: FloatArray) -> FloatArray:
        if (
            self.feature_mean is None
            or self.feature_scale is None
            or self.coefficients is None
            or self.intercept is None
        ):
            raise RuntimeError("fit must be called before predict")
        x = np.asarray(features, dtype=float)
        standardized = (x - self.feature_mean) / self.feature_scale
        predictions = self.intercept + standardized @ self.coefficients
        return np.clip(predictions, 0.0, 1.0).astype(np.float64)

    def rmse(self, features: FloatArray, target: FloatArray) -> float:
        errors = self.predict(features) - np.asarray(target, dtype=float)
        return float(np.sqrt(np.mean(errors**2)))


@dataclass
class EWMAResidualMonitor:
    """Online residual monitor for sensor-bias and model-mismatch alarms."""

    smoothing: float = 0.15
    alarm_threshold: float = 0.025
    value: float = 0.0
    initialized: bool = False

    def update(self, residual: float) -> tuple[float, bool]:
        if not 0.0 < self.smoothing <= 1.0:
            raise ValueError("smoothing must be in (0, 1]")
        self.value = (
            float(residual)
            if not self.initialized
            else self.smoothing * float(residual) + (1.0 - self.smoothing) * self.value
        )
        self.initialized = True
        return self.value, abs(self.value) >= self.alarm_threshold
