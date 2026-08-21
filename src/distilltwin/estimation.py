"""Measurement models and nonlinear state estimation for the column."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from distilltwin.model import ColumnInputs, DistillationColumn

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class MeasurementConfig:
    """Measured stage signals and their one-standard-deviation noise levels."""

    composition_stages: tuple[int, ...] = (7, 0)
    temperature_stages: tuple[int, ...] = (2, 5)
    composition_noise_std: float = 0.002
    temperature_noise_std: float = 0.08

    def __post_init__(self) -> None:
        stages = self.composition_stages + self.temperature_stages
        if not stages:
            raise ValueError("at least one measurement is required")
        if any(stage < 0 for stage in stages):
            raise ValueError("measurement stage indices must be nonnegative")
        if len(set(self.composition_stages)) != len(self.composition_stages):
            raise ValueError("composition stage indices must be unique")
        if len(set(self.temperature_stages)) != len(self.temperature_stages):
            raise ValueError("temperature stage indices must be unique")
        noise = np.asarray(
            [self.composition_noise_std, self.temperature_noise_std], dtype=float
        )
        if not np.all(np.isfinite(noise)) or np.any(noise <= 0.0):
            raise ValueError("measurement noise standard deviations must be finite and positive")


class MeasurementModel:
    """Map the full column state to a configurable subset of plant measurements."""

    def __init__(
        self,
        column: DistillationColumn,
        config: MeasurementConfig | None = None,
    ) -> None:
        self.column = column
        self.config = config or MeasurementConfig()
        stages = self.config.composition_stages + self.config.temperature_stages
        if any(stage >= column.config.n_stages for stage in stages):
            raise ValueError("measurement stage index exceeds the column state dimension")

    @property
    def size(self) -> int:
        return len(self.config.composition_stages) + len(self.config.temperature_stages)

    @property
    def covariance(self) -> FloatArray:
        diagonal = [
            *(self.config.composition_noise_std**2 for _ in self.config.composition_stages),
            *(self.config.temperature_noise_std**2 for _ in self.config.temperature_stages),
        ]
        return np.diag(diagonal).astype(np.float64)

    def observe(self, state: FloatArray) -> FloatArray:
        """Return noise-free measurements without exposing unmeasured stages."""
        x = self.column.validate_state(state)
        compositions = x[np.asarray(self.config.composition_stages, dtype=int)]
        temperatures = self.column.temperature_proxy(x)[
            np.asarray(self.config.temperature_stages, dtype=int)
        ]
        return np.concatenate([compositions, temperatures]).astype(np.float64)

    def sample(
        self,
        state: FloatArray,
        rng: np.random.Generator,
        *,
        noise_scale: float = 1.0,
    ) -> FloatArray:
        """Return a reproducible noisy measurement vector."""
        if not np.isfinite(noise_scale) or noise_scale < 0.0:
            raise ValueError("noise_scale must be finite and nonnegative")
        standard_deviations = np.sqrt(np.diag(self.covariance)) * noise_scale
        return (self.observe(state) + rng.normal(0.0, standard_deviations)).astype(
            np.float64
        )

    def jacobian(self) -> FloatArray:
        """Return the exact measurement Jacobian for composition and temperature signals."""
        matrix = np.zeros((self.size, self.column.config.n_stages), dtype=float)
        for row, stage in enumerate(self.config.composition_stages):
            matrix[row, stage] = 1.0
        offset = len(self.config.composition_stages)
        for row, stage in enumerate(self.config.temperature_stages, start=offset):
            matrix[row, stage] = -30.5
        return matrix.astype(np.float64)


@dataclass(frozen=True)
class EKFConfig:
    """Numerical tuning for the discrete-time extended Kalman filter."""

    process_noise_std: float = 3e-4
    initial_state_std: float = 0.04
    covariance_floor: float = 1e-12

    def __post_init__(self) -> None:
        values = np.asarray(
            [
                self.process_noise_std,
                self.initial_state_std,
                self.covariance_floor,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("EKF tuning values must be finite and positive")


@dataclass(frozen=True)
class CorrectionResult:
    """State and pre-fit innovation returned by one measurement correction."""

    state: FloatArray
    innovation: FloatArray


def discrete_transition_jacobian(
    column: DistillationColumn,
    state: FloatArray,
    inputs: ColumnInputs,
    dt: float,
) -> FloatArray:
    """Propagate the analytical balance Jacobian through one RK4 transition."""
    x = column.validate_state(state)
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt must be finite and positive")
    identity = np.eye(column.config.n_stages, dtype=float)

    k1 = column.derivatives(x, inputs)
    a1 = column.derivative_jacobian(x, inputs)
    state2 = x + 0.5 * dt * k1
    state2_sensitivity = identity + 0.5 * dt * a1
    k2 = column.derivatives(state2, inputs)
    k2_sensitivity = column.derivative_jacobian(state2, inputs) @ state2_sensitivity

    state3 = x + 0.5 * dt * k2
    state3_sensitivity = identity + 0.5 * dt * k2_sensitivity
    k3 = column.derivatives(state3, inputs)
    k3_sensitivity = column.derivative_jacobian(state3, inputs) @ state3_sensitivity

    state4 = x + dt * k3
    state4_sensitivity = identity + dt * k3_sensitivity
    k4_sensitivity = column.derivative_jacobian(state4, inputs) @ state4_sensitivity
    jacobian = identity + dt * (
        a1 + 2.0 * k2_sensitivity + 2.0 * k3_sensitivity + k4_sensitivity
    ) / 6.0
    if not np.all(np.isfinite(jacobian)):
        raise FloatingPointError("state-transition linearization produced non-finite values")
    return jacobian.astype(np.float64)


class ExtendedKalmanFilter:
    """Discrete EKF around the nonlinear RK4 column transition."""

    def __init__(
        self,
        column: DistillationColumn,
        measurements: MeasurementModel,
        *,
        initial_state: FloatArray | None = None,
        config: EKFConfig | None = None,
    ) -> None:
        if measurements.column.config.n_stages != column.config.n_stages:
            raise ValueError("measurement and transition models must have equal dimensions")
        self.column = column
        self.measurements = measurements
        self.config = config or EKFConfig()
        start = column.steady_state() if initial_state is None else initial_state
        self.state = column.validate_state(start).copy()
        variance = self.config.initial_state_std**2
        self.covariance = np.eye(column.config.n_stages, dtype=float) * variance

    def predict(self, inputs: ColumnInputs, dt: float) -> FloatArray:
        """Propagate the state and covariance through the nonlinear model."""
        transition = discrete_transition_jacobian(
            self.column,
            self.state,
            inputs,
            dt,
        )
        predicted = self.column.step(self.state, inputs, dt)
        process_covariance = (
            np.eye(self.column.config.n_stages, dtype=float)
            * self.config.process_noise_std**2
            * dt
        )
        covariance = transition @ self.covariance @ transition.T + process_covariance
        self.state = predicted
        self.covariance = self._stabilize_covariance(covariance)
        return self.state.copy()

    def correct(self, measurement: FloatArray) -> CorrectionResult:
        """Correct the predicted state using the measured subset of signals."""
        observed = np.asarray(measurement, dtype=float)
        if observed.shape != (self.measurements.size,):
            raise ValueError(f"measurement must have shape ({self.measurements.size},)")
        if not np.all(np.isfinite(observed)):
            raise ValueError("measurement must contain only finite values")

        measurement_jacobian = self.measurements.jacobian()
        innovation = observed - self.measurements.observe(self.state)
        innovation_covariance = (
            measurement_jacobian @ self.covariance @ measurement_jacobian.T
            + self.measurements.covariance
        )
        cross_covariance = self.covariance @ measurement_jacobian.T
        kalman_gain = np.linalg.solve(
            innovation_covariance, cross_covariance.T
        ).T
        corrected = np.clip(self.state + kalman_gain @ innovation, 0.0, 1.0)

        identity = np.eye(self.column.config.n_stages, dtype=float)
        residual_projection = identity - kalman_gain @ measurement_jacobian
        covariance = (
            residual_projection @ self.covariance @ residual_projection.T
            + kalman_gain @ self.measurements.covariance @ kalman_gain.T
        )
        self.state = corrected.astype(np.float64)
        self.covariance = self._stabilize_covariance(covariance)
        return CorrectionResult(self.state.copy(), innovation.astype(np.float64))

    def _stabilize_covariance(self, covariance: FloatArray) -> FloatArray:
        symmetric = 0.5 * (covariance + covariance.T)
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        floored = np.maximum(eigenvalues, self.config.covariance_floor)
        stable = (eigenvectors * floored) @ eigenvectors.T
        if not np.all(np.isfinite(stable)):
            raise FloatingPointError("EKF covariance produced non-finite values")
        stabilized: FloatArray = stable.astype(np.float64)
        return stabilized


def local_observability_rank(
    column: DistillationColumn,
    measurements: MeasurementModel,
    state: FloatArray,
    inputs: ColumnInputs,
    dt: float,
) -> int:
    """Return the rank of the local discrete linear observability matrix."""
    transition = discrete_transition_jacobian(column, state, inputs, dt)
    measurement_jacobian = measurements.jacobian()
    blocks = []
    power = np.eye(column.config.n_stages, dtype=float)
    for _ in range(column.config.n_stages):
        blocks.append(measurement_jacobian @ power)
        power = power @ transition
    return int(np.linalg.matrix_rank(np.vstack(blocks)))
