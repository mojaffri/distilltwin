"""Reproducible state-estimation experiments with a hidden simulated plant."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

import numpy as np
import pandas as pd

from distilltwin.estimation import (
    EKFConfig,
    ExtendedKalmanFilter,
    MeasurementConfig,
    MeasurementModel,
    local_observability_rank,
)
from distilltwin.model import ColumnConfig, ColumnInputs, DistillationColumn


@dataclass(frozen=True)
class EstimationScenario:
    """Plant disturbance, noise, and mismatch settings for an EKF experiment."""

    name: str
    duration: float = 24.0
    dt: float = 0.2
    disturbance_at: float = 8.0
    feed_composition_after: float = 0.50
    feed_rate_after: float = 1.0
    measurement_noise_scale: float = 1.0
    plant_relative_volatility: float | None = None
    plant_holdup_scale: float = 1.0
    estimator_knows_feed_composition: bool = True
    estimator_knows_feed_rate: bool = True
    random_seed: int = 20260820

    def __post_init__(self) -> None:
        values = (
            self.duration,
            self.dt,
            self.disturbance_at,
            self.feed_composition_after,
            self.feed_rate_after,
            self.measurement_noise_scale,
            self.plant_holdup_scale,
        )
        if not self.name:
            raise ValueError("scenario name must not be empty")
        if not all(isfinite(value) for value in values):
            raise ValueError("estimation scenario values must be finite")
        if self.duration <= 0.0 or self.dt <= 0.0:
            raise ValueError("duration and dt must be positive")
        if not 0.0 <= self.disturbance_at <= self.duration:
            raise ValueError("disturbance_at must fall within the simulation")
        if not 0.0 <= self.feed_composition_after <= 1.0:
            raise ValueError("feed composition must be between zero and one")
        if self.feed_rate_after <= 0.0:
            raise ValueError("feed rate must be positive")
        if self.measurement_noise_scale < 0.0:
            raise ValueError("measurement noise scale must be nonnegative")
        if self.plant_holdup_scale <= 0.0:
            raise ValueError("plant holdup scale must be positive")
        if self.plant_relative_volatility is not None and (
            not isfinite(self.plant_relative_volatility)
            or self.plant_relative_volatility <= 1.0
        ):
            raise ValueError("plant relative volatility must be finite and above one")


@dataclass(frozen=True)
class EstimationMetrics:
    """State reconstruction errors for one defined experiment."""

    overall_rmse: float
    post_disturbance_rmse: float
    transient_rmse: float
    peak_state_rmse: float
    convergence_delay: float
    converged: bool
    per_stage_rmse: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "overall_rmse": self.overall_rmse,
            "post_disturbance_rmse": self.post_disturbance_rmse,
            "transient_rmse": self.transient_rmse,
            "peak_state_rmse": self.peak_state_rmse,
            "convergence_delay": self.convergence_delay,
            "converged": self.converged,
            "per_stage_rmse": list(self.per_stage_rmse),
        }


@dataclass(frozen=True)
class EstimationCaseResult:
    """Metrics and local observability result for one scenario."""

    scenario: EstimationScenario
    metrics: EstimationMetrics
    observability_rank: int

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario.name,
            "observability_rank": self.observability_rank,
            **self.metrics.to_dict(),
        }


@dataclass(frozen=True)
class EstimationBenchmark:
    """Complete deterministic EKF benchmark across defined operating cases."""

    state_dimension: int
    measured_signal_count: int
    composition_stages: tuple[int, ...]
    temperature_stages: tuple[int, ...]
    cases: tuple[EstimationCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "state_dimension": self.state_dimension,
            "measured_signal_count": self.measured_signal_count,
            "composition_stages": list(self.composition_stages),
            "temperature_stages": list(self.temperature_stages),
            "cases": [case.to_dict() for case in self.cases],
        }

    def rows(self) -> list[dict[str, float | int | str | bool]]:
        rows: list[dict[str, float | int | str | bool]] = []
        for case in self.cases:
            common: dict[str, float | int | str | bool] = {
                "scenario": case.scenario.name,
                "observability_rank": case.observability_rank,
                "overall_rmse": case.metrics.overall_rmse,
                "post_disturbance_rmse": case.metrics.post_disturbance_rmse,
                "transient_rmse": case.metrics.transient_rmse,
                "peak_state_rmse": case.metrics.peak_state_rmse,
                "convergence_delay": case.metrics.convergence_delay,
                "converged": case.metrics.converged,
            }
            for stage, rmse in enumerate(case.metrics.per_stage_rmse):
                rows.append({**common, "stage": stage, "stage_rmse": rmse})
        return rows


def _plant_config(scenario: EstimationScenario) -> ColumnConfig:
    base = ColumnConfig()
    alpha = (
        base.relative_volatility
        if scenario.plant_relative_volatility is None
        else scenario.plant_relative_volatility
    )
    scale = scenario.plant_holdup_scale
    return replace(
        base,
        relative_volatility=alpha,
        tray_holdup=base.tray_holdup * scale,
        condenser_holdup=base.condenser_holdup * scale,
        reboiler_holdup=base.reboiler_holdup * scale,
    )


def _metrics(
    frame: pd.DataFrame,
    *,
    n_stages: int,
    disturbance_at: float,
    convergence_tolerance: float = 0.02,
) -> EstimationMetrics:
    true_state = frame[[f"true_x_{stage}" for stage in range(n_stages)]].to_numpy(
        dtype=float
    )
    estimated_state = frame[
        [f"estimated_x_{stage}" for stage in range(n_stages)]
    ].to_numpy(dtype=float)
    errors = estimated_state - true_state
    times = frame["time"].to_numpy(dtype=float)
    state_rmse = np.sqrt(np.mean(errors**2, axis=1))
    post_mask = times >= disturbance_at
    transient_mask = (times >= disturbance_at) & (times <= disturbance_at + 5.0)
    suffix_peak = np.maximum.accumulate(state_rmse[::-1])[::-1]
    converged_indices = np.flatnonzero(post_mask & (suffix_peak <= convergence_tolerance))
    converged = bool(len(converged_indices))
    convergence_delay = (
        float(times[converged_indices[0]] - disturbance_at)
        if converged
        else float(times[-1] - disturbance_at)
    )
    return EstimationMetrics(
        overall_rmse=float(np.sqrt(np.mean(errors**2))),
        post_disturbance_rmse=float(np.sqrt(np.mean(errors[post_mask] ** 2))),
        transient_rmse=float(np.sqrt(np.mean(errors[transient_mask] ** 2))),
        peak_state_rmse=float(np.max(state_rmse)),
        convergence_delay=convergence_delay,
        converged=converged,
        per_stage_rmse=tuple(
            float(value) for value in np.sqrt(np.mean(errors**2, axis=0))
        ),
    )


def run_estimation_case(
    scenario: EstimationScenario,
    measurement_config: MeasurementConfig | None = None,
) -> tuple[EstimationCaseResult, pd.DataFrame]:
    """Run one hidden-plant experiment and return metrics plus its trajectory."""
    twin = DistillationColumn()
    plant = DistillationColumn(_plant_config(scenario))
    config = measurement_config or MeasurementConfig()
    measurements = MeasurementModel(twin, config)
    plant_state = plant.steady_state()
    initial_offset = np.linspace(0.035, -0.035, twin.config.n_stages, dtype=float)
    initial_estimate = np.clip(twin.steady_state() + initial_offset, 0.0, 1.0)
    estimator = ExtendedKalmanFilter(
        twin,
        measurements,
        initial_state=initial_estimate,
        config=EKFConfig(),
    )
    rng = np.random.default_rng(scenario.random_seed)
    records: list[dict[str, float]] = []

    for time in np.arange(0.0, scenario.duration + scenario.dt / 2.0, scenario.dt):
        disturbed = time >= scenario.disturbance_at
        plant_inputs = ColumnInputs(
            feed_rate=scenario.feed_rate_after if disturbed else 1.0,
            feed_composition=(
                scenario.feed_composition_after if disturbed else 0.50
            ),
            reflux_flow=2.50,
            boilup_flow=3.00,
        )
        estimator_inputs = ColumnInputs(
            feed_rate=(
                plant_inputs.feed_rate
                if scenario.estimator_knows_feed_rate
                else 1.0
            ),
            feed_composition=(
                plant_inputs.feed_composition
                if scenario.estimator_knows_feed_composition
                else 0.50
            ),
            reflux_flow=plant_inputs.reflux_flow,
            boilup_flow=plant_inputs.boilup_flow,
        )
        measured = measurements.sample(
            plant_state,
            rng,
            noise_scale=scenario.measurement_noise_scale,
        )
        estimated_state = estimator.correct(measured).state
        record: dict[str, float] = {"time": float(time)}
        for stage in range(twin.config.n_stages):
            record[f"true_x_{stage}"] = float(plant_state[stage])
            record[f"estimated_x_{stage}"] = float(estimated_state[stage])
        records.append(record)
        plant_state = plant.step(plant_state, plant_inputs, scenario.dt)
        estimator.predict(estimator_inputs, scenario.dt)

    frame = pd.DataFrame.from_records(records)
    rank = local_observability_rank(
        twin,
        measurements,
        twin.steady_state(),
        twin.nominal_inputs,
        scenario.dt,
    )
    result = EstimationCaseResult(
        scenario=scenario,
        metrics=_metrics(
            frame,
            n_stages=twin.config.n_stages,
            disturbance_at=scenario.disturbance_at,
        ),
        observability_rank=rank,
    )
    return result, frame


def benchmark_state_estimator() -> EstimationBenchmark:
    """Evaluate the EKF under nominal, disturbance, noise, and mismatch cases."""
    scenarios = (
        EstimationScenario(name="nominal"),
        EstimationScenario(
            name="unmeasured feed composition step",
            feed_composition_after=0.62,
            estimator_knows_feed_composition=False,
        ),
        EstimationScenario(
            name="unmeasured feed rate step",
            feed_rate_after=1.15,
            estimator_knows_feed_rate=False,
        ),
        EstimationScenario(name="sensor noise", measurement_noise_scale=3.0),
        EstimationScenario(
            name="model mismatch",
            feed_composition_after=0.62,
            plant_relative_volatility=2.20,
            plant_holdup_scale=1.15,
            estimator_knows_feed_composition=False,
        ),
    )
    config = MeasurementConfig()
    cases = tuple(run_estimation_case(case, config)[0] for case in scenarios)
    return EstimationBenchmark(
        state_dimension=ColumnConfig().n_stages,
        measured_signal_count=len(config.composition_stages)
        + len(config.temperature_stages),
        composition_stages=config.composition_stages,
        temperature_stages=config.temperature_stages,
        cases=cases,
    )
