"""Feedback-control primitives with saturation and anti-windup."""

from __future__ import annotations

from dataclasses import dataclass


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

    def update(self, *, setpoint: float, measurement: float, dt: float) -> float:
        if dt <= 0:
            raise ValueError("dt must be positive")
        cfg = self.config
        error = setpoint - measurement
        derivative = 0.0 if self.previous_error is None else (error - self.previous_error) / dt
        candidate_integral = self.integral + error * dt
        raw = cfg.bias + cfg.action * (
            cfg.kp * error + cfg.ki * candidate_integral + cfg.kd * derivative
        )
        output = min(cfg.output_max, max(cfg.output_min, raw))

        pushing_high = raw > cfg.output_max and cfg.action * error > 0
        pushing_low = raw < cfg.output_min and cfg.action * error < 0
        if not (pushing_high or pushing_low):
            self.integral = candidate_integral
        self.previous_error = error
        return output

