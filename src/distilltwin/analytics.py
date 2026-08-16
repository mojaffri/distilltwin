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
            else self.smoothing * float(residual) + (1.0 - self.…2479 tokens truncated…o an illustrative normal-boiling temperature signal in Celsius."""
        x = np.asarray(liquid_composition, dtype=float)
        return 110.6 - 30.5 * x

    def derivatives(self, state: FloatArray, inputs: ColumnInputs) -> FloatArray:
        """Evaluate stage light-key component balances."""
        inputs.validate()
        cfg = self.config
        x = np.asarray(state, dtype=float)
        if x.shape != (cfg.n_stages,):
            raise ValueError(f"state must have shape ({cfg.n_stages},)")

        y = self.equilibrium_vapor(x)
        derivative = np.zeros_like(x)
        feed = inputs.feed_rate
        reflux = inputs.reflux_flow
        vapor = inputs.boilup_flow
        bottoms = reflux + feed - vapor

        liquid_from_above = reflux + feed
        derivative[0] = (
            liquid_from_above * x[1] - bottoms * x[0] - vapor * y[0]
        ) / cfg.reboiler_holdup

        for stage in range(1, cfg.n_stages - 1):
            liquid_out = reflux + feed if stage <= cfg.feed_stage else reflux
            liquid_in = reflux + feed if stage + 1 <= cfg.feed_stage else reflux
            feed_component = feed * inputs.feed_composition if stage == cfg.feed_stage else 0.0
            derivative[stage] = (
                liquid_in * x[stage + 1]
                + vapor * y[stage - 1]
                + feed_component
                - liquid_out * x[stage]
                - vapor * y[stage]
            ) / cfg.tray_holdup

        derivative[-1] = vapor * (y[-2] - x[-1]) / cfg.condenser_holdup
        return derivative

    def step(self, state: FloatArray, inputs: ColumnInputs, dt: float) -> FloatArray:
        """Advance the model one step with fourth-order Runge-Kutta integration."""
        if dt <= 0:
            raise ValueError("dt must be positive")
        x = np.asarray(state, dtype=float)
        k1 = self.derivatives(x, inputs)
        k2 = self.derivatives(x + 0.5 * dt * k1, inputs)
        k3 = self.derivatives(x + 0.5 * dt * k2, inputs)
        k4 = self.derivatives(x + dt * k3, inputs)
        next_state = x + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        return np.clip(next_state, 0.0, 1.0).astype(np.float64)

    def steady_state(
        self,
        inputs: ColumnInputs | None = None,
        *,
        tolerance: float = 1e-9,
        max_steps: int = 50_000,
    ) -> FloatArray:
        """Numerically settle the column at fixed inputs."""
        fixed_inputs = inputs or self.nominal_inputs
        state = np.linspace(0.08, 0.92, self.config.n_stages, dtype=float)
        for _ in range(max_steps):
            updated = self.step(state, fixed_inputs, 0.05)
            if float(np.max(np.abs(updated - state))) < tolerance:
                return updated
            state = updated
        raise RuntimeError("steady-state solver did not converge")

    def simulate(
        self,
        input_schedule: Callable[[float], ColumnInputs],
        *,
        duration: float,
        dt: float = 0.1,
        initial_state: FloatArray | None = None,
    ) -> pd.DataFrame:
        """Run an open-loop simulation and return a tidy time-series frame."""
        if duration <= 0:
            raise ValueError("duration must be positive")
        state = (
            self.steady_state()
            if initial_state is None
            else np.asarray(initial_state, dtype=float)
        )
        records: list[dict[str, float]] = []
        for time in np.arange(0.0, duration + dt / 2.0, dt):
            inputs = input_schedule(float(time))
            temperatures = self.temperature_proxy(state)
            records.append(
                {
                    "time": float(time),
                    "x_bottom": float(state[0]),
                    "x_top": float(state[-1]),
                    "temperature_bottom": float(temperatures[0]),
                    "temperature_top": float(temperatures[-1]),
                    "feed_rate": inputs.feed_rate,
                    "feed_composition": inputs.feed_composition,
                    "reflux_flow": inputs.reflux_flow,
                    "boilup_flow": inputs.boilup_flow,
                }
            )
            state = self.step(state, inputs, dt)
        return pd.DataFrame.from_records(records)
