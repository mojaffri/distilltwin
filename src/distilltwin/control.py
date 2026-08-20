"""Feedback-control primitives with saturation and anti-windup."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class PIDConfig:
    kp: float
    ki: float
    kd: float = 0.0
    output_min: float = 0.0
    output_max: float = 1.0
    bias: float = 0.0
    action: float = 1.0

    def __post_init__(self) -> None:
        values = (self.kp, self.ki, self.kd, self.output_min, self.output_max, self.bias)
        if not all(isfinite(value) for value in values):
            raise ValueError("PID configuration values must be finite")
        if self.output_min >= self.output_max:
            raise ValueError("output_min must be below output_max")
        if self.action not in (-1.0, 1.0):
            raise ValueError("action must be +1 (direct) or -1 (reverse)")


class PIDController:
    """Parallel-form PID controller with conditional-integration anti-windup."""

    def __init__(self, config: PIDConfig) -> None:
        self.config = config
        self.integral = 0.0
        self.previous_error: float | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_error = None

    def update(
        self,
        *,
        setpoint: float,
        measurement: float,
        dt: float,
        output_min: float | None = None,
        output_max: float | None = None,
    ) -> float:
        if not all(isfinite(value) for value in (setpoint, measurement, dt)) or dt <= 0:
            raise ValueError("setpoint, measurement, and positive dt must be finite")
        cfg = self.config
        lower = cfg.output_min if output_min is None else output_min
        upper = cfg.output_max if output_max is None else output_max
        if not isfinite(lower) or not isfinite(upper) or lower >= upper:
            raise ValueError("active output limits must be finite and ordered")
        error = setpoint - measurement
        derivative = 0.0 if self.previous_error is None else (error - self.previous_error) / dt
        candidate_integral = self.integral + error * dt
        raw = cfg.bias + cfg.action * (
            cfg.kp * error + cfg.ki * candidate_integral + cfg.kd * derivative
        )
        output = min(upper, max(lower, raw))

        pushing_high = raw > upper and cfg.action * error > 0
        pushing_low = raw < lower and cfg.action * error < 0
        if not (pushing_high or pushing_low):
            self.integral = candidate_integral
        self.previous_error = error
        return output

