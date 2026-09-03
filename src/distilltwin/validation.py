"""Reproducible, Aspen-independent validation for the open DistillTwin model.

These checks establish numerical consistency and control/fault performance inside the
stated reduced-order assumptions. They do not claim agreement with a commercial
simulator or plant data.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from distilltwin.analytics import RidgeSoftSensor
from distilltwin.model import ColumnInputs, DistillationColumn
from distilltwin.scenarios import Scenario, ScenarioRunner

SOFT_SENSOR_FEATURES = (
    "temperature_bottom",
    "temperature_lower_tray",
    "temperature_upper_tray",
    "feed_rate",
    "feed_composition",
    "reflux_flow",
    "boilup_flow",
)


@dataclass(frozen=True)
class ResponseMetrics:
    """Integral and transient metrics for one controlled variable."""

    iae: float
    ise: float
    peak_absolute_error: float
    final_absolute_error: float
    settling_time: float
    settled: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "iae": self.iae,
            "ise": self.ise,
            "peak_absolute_error": self.peak_absolute_error,
            "final_absolute_error": self.final_absolute_error,
            "settling_time": self.settling_time,
            "settled": self.settled,
        }


@dataclass(frozen=True)
class ControlBenchmark:
    """Open-loop and closed-loop disturbance-rejection evidence."""

    open_loop_top: ResponseMetrics
    closed_loop_top: ResponseMetrics
    open_loop_bottom: ResponseMetrics
    closed_loop_bottom: ResponseMetrics

    def rows(self) -> list[dict[str, float | str | bool]]:
        rows: list[dict[str, float | str | bool]] = []
        for mode, variable, metrics in (
            ("open loop", "top composition", self.open_loop_top),
            ("paired PID", "top composition", self.closed_loop_top),
            ("open loop", "bottom composition", self.open_loop_bottom),
            ("paired PID", "bottom composition", self.closed_loop_bottom),
        ):
            rows.append({"mode": mode, "variable": variable, **metrics.to_dict()})
        return rows

    def to_dict(self) -> dict[str, object]:
        return {
            "open_loop_top": self.open_loop_top.to_dict(),
            "closed_loop_top": self.closed_loop_top.to_dict(),
            "open_loop_bottom": self.open_loop_bottom.to_dict(),
            "closed_loop_bottom": self.closed_loop_bottom.to_dict(),
        }


@dataclass(frozen=True)
class PhysicsValidation:
    """Conservation, stationarity, and physical-domain checks."""

    material_balance_absolute_residual: float
    steady_state_max_derivative: float
    steady_state_min_composition: float
    steady_state_max_composition: float
    steady_state_monotonic: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "material_balance_absolute_residual": self.material_balance_absolute_residual,
            "steady_state_max_derivative": self.steady_state_max_derivative,
            "steady_state_min_composition": self.steady_state_min_composition,
            "steady_state_max_composition": self.steady_state_max_composition,
            "steady_state_monotonic": self.steady_state_monotonic,
        }


@dataclass(frozen=True)
class TimestepCase:
    """Difference from the finest numerical reference at one timestep."""

    dt: float
    samples: int
    final_top_absolute_difference: float
    final_bottom_absolute_difference: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "dt": self.dt,
            "samples": self.samples,
            "final_top_absolute_difference": self.final_top_absolute_difference,
            "final_bottom_absolute_difference": self.final_bottom_absolute_difference,
        }


@dataclass(frozen=True)
class FaultDetectionMetrics:
    """Detection behavior for a known persistent top-analyzer bias."""

    injected_bias: float
    detection_delay: float
    false_alarm_fraction: float
    post_fault_alarm_fraction: float
    detected: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "injected_bias": self.injected_bias,
            "detection_delay": self.detection_delay,
            "false_alarm_fraction": self.false_alarm_fraction,
            "post_fault_alarm_fraction": self.post_fault_alarm_fraction,
            "detected": self.detected,
        }


@dataclass(frozen=True)
class SoftSensorMetrics:
    """Generalization evidence for the process-context ridge soft sensor."""

    training_scenarios: int
    holdout_scenarios: int
    training_samples: int
    holdout_samples: int
    temperature_noise_std_c: float
    rmse: float
    mae: float
    constant_baseline_rmse: float
    rmse_improvement_fraction: float

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "training_scenarios": self.training_scenarios,
            "holdout_scenarios": self.holdout_scenarios,
            "training_samples": self.training_samples,
            "holdout_samples": self.holdout_samples,
            "temperature_noise_std_c": self.temperature_noise_std_c,
            "rmse": self.rmse,
            "mae": self.mae,
            "constant_baseline_rmse": self.constant_baseline_rmse,
            "rmse_improvement_fraction": self.rmse_improvement_fraction,
            "scenario_level_holdout": True,
        }


@dataclass(frozen=True)
class FaultCaseMetrics:
    """Monte Carlo detection results for one noisy analyzer-fault family."""

    fault: str
    magnitude: float
    units: str
    replicates: int
    detection_rate: float
    median_detection_delay: float
    p95_detection_delay: float
    pre_fault_false_alarm_fraction: float
    post_fault_alarm_fraction: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "fault": self.fault,
            "magnitude": self.magnitude,
            "units": self.units,
            "replicates": self.replicates,
            "detection_rate": self.detection_rate,
            "median_detection_delay": self.median_detection_delay,
            "p95_detection_delay": self.p95_detection_delay,
            "pre_fault_false_alarm_fraction": self.pre_fault_false_alarm_fraction,
            "post_fault_alarm_fraction": self.post_fault_alarm_fraction,
        }


@dataclass(frozen=True)
class FaultSuiteMetrics:
    """Noise-robust benchmark across abrupt and incipient analyzer faults."""

    noise_standard_deviation: float
    no_fault_alarm_fraction: float
    cases: tuple[FaultCaseMetrics, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "noise_standard_deviation": self.noise_standard_deviation,
            "no_fault_alarm_fraction": self.no_fault_alarm_fraction,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass(frozen=True)
class ValidationReport:
    """Complete deterministic validation result."""

    physics: PhysicsValidation
    control: ControlBenchmark
    timestep_reference_dt: float
    timestep_cases: tuple[TimestepCase, ...]
    fault_detection: FaultDetectionMetrics
    soft_sensor: SoftSensorMetrics
    fault_suite: FaultSuiteMetrics

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": (
                "Aspen-independent verification of the reduced-order model; "
                "not commercial-simulator or plant validation"
            ),
            "physics": self.physics.to_dict(),
            "control": self.control.to_dict(),
            "numerics": {
                "reference_dt": self.timestep_reference_dt,
                "cases": [case.to_dict() for case in self.timestep_cases],
            },
            "fault_detection": self.fault_detection.to_dict(),
            "soft_sensor": self.soft_sensor.to_dict(),
            "fault_suite": self.fault_suite.to_dict(),
        }


def response_metrics(
    frame: pd.DataFrame,
    *,
    value_column: str,
    setpoint_column: str,
    disturbance_at: float,
    settling_tolerance: float = 0.01,
) -> ResponseMetrics:
    """Calculate standard transient response metrics after a disturbance."""
    post = frame.loc[frame["time"] >= disturbance_at]
    if post.empty:
        raise ValueError("frame must contain samples at or after disturbance_at")
    time = post["time"].to_numpy(dtype=float)
    error = (
        post[value_column].to_numpy(dtype=float)
        - post[setpoint_column].to_numpy(dtype=float)
    )
    absolute_error = np.abs(error)
    suffix_peak = np.maximum.accumulate(absolute_error[::-1])[::-1]
    settled_indices = np.flatnonzero(suffix_peak <= settling_tolerance)
    settled = bool(len(settled_indices))
    settling_time = (
        float(time[settled_indices[0]] - disturbance_at)
        if settled
        else float(time[-1] - disturbance_at)
    )
    return ResponseMetrics(
        iae=float(np.trapezoid(absolute_error, time)),
        ise=float(np.trapezoid(error**2, time)),
        peak_absolute_error=float(absolute_error.max()),
        final_absolute_error=float(absolute_error[-1]),
        settling_time=settling_time,
        settled=settled,
    )


def run_open_loop(scenario: Scenario, column: DistillationColumn | None = None) -> pd.DataFrame:
    """Run the same feed disturbance at fixed nominal manipulated variables."""
    model = column or DistillationColumn()
    initial_state = model.steady_state()
    top_setpoint = float(initial_state[-1])
    bottom_setpoint = float(initial_state[0])
    cfg = model.config

    def schedule(time: float) -> ColumnInputs:
        disturbed = time >= scenario.disturbance_at
        return ColumnInputs(
            feed_rate=scenario.feed_rate_after if disturbed else cfg.nominal_feed,
            feed_composition=(
                scenario.feed_composition_after
                if disturbed
                else cfg.nominal_feed_composition
            ),
            reflux_flow=cfg.nominal_reflux,
            boilup_flow=cfg.nominal_boilup,
        )

    frame = model.simulate(
        schedule,
        duration=scenario.duration,
        dt=scenario.dt,
        initial_state=initial_state,
    )
    frame["top_setpoint"] = top_setpoint
    frame["bottom_setpoint"] = bottom_setpoint
    return frame


def benchmark_control(scenario: Scenario | None = None) -> ControlBenchmark:
    """Compare paired PID control with fixed-input open-loop operation."""
    case = scenario or Scenario(
        duration=40.0,
        dt=0.1,
        disturbance_at=10.0,
        feed_composition_after=0.62,
    )
    if case.top_sensor_bias_after != 0.0 or case.reflux_effectiveness_after != 1.0:
        raise ValueError("control benchmark must not include sensor or actuator faults")
    open_loop = run_open_loop(case)
    closed_loop = ScenarioRunner().run(case)
    arguments = {"disturbance_at": case.disturbance_at}
    return ControlBenchmark(
        open_loop_top=response_metrics(
            open_loop,
            value_column="x_top",
            setpoint_column="top_setpoint",
            **arguments,
        ),
        closed_loop_top=response_metrics(
            closed_loop,
            value_column="x_top",
            setpoint_column="top_setpoint",
            **arguments,
        ),
        open_loop_bottom=response_metrics(
            open_loop,
            value_column="x_bottom",
            setpoint_column="bottom_setpoint",
            **arguments,
        ),
        closed_loop_bottom=response_metrics(
            closed_loop,
            value_column="x_bottom",
            setpoint_column="bottom_setpoint",
            **arguments,
        ),
    )


def validate_physics(column: DistillationColumn | None = None) -> PhysicsValidation:
    """Quantify balance closure and nominal steady-state stationarity."""
    model = column or DistillationColumn()
    state = np.linspace(0.1, 0.9, model.config.n_stages)
    inputs = model.nominal_inputs
    rates = model.derivatives(state, inputs)
    holdups = np.full(model.config.n_stages, model.config.tray_holdup)
    holdups[0] = model.config.reboiler_holdup
    holdups[-1] = model.config.condenser_holdup
    accumulation = float(rates @ holdups)
    distillate = inputs.boilup_flow - inputs.reflux_flow
    bottoms = inputs.reflux_flow + inputs.feed_rate - inputs.boilup_flow
    boundary_flux = (
        inputs.feed_rate * inputs.feed_composition
        - distillate * state[-1]
        - bottoms * state[0]
    )

    steady_state = model.steady_state()
    steady_residual = model.derivatives(steady_state, inputs)
    return PhysicsValidation(
        material_balance_absolute_residual=abs(accumulation - boundary_flux),
        steady_state_max_derivative=float(np.max(np.abs(steady_residual))),
        steady_state_min_composition=float(steady_state.min()),
        steady_state_max_composition=float(steady_state.max()),
        steady_state_monotonic=bool(np.all(np.diff(steady_state) > 0.0)),
    )


def benchmark_timesteps(
    scenario: Scenario | None = None,
    *,
    timesteps: tuple[float, ...] = (0.4, 0.2, 0.1),
    reference_dt: float = 0.05,
) -> tuple[TimestepCase, ...]:
    """Compare final products with a finer RK4 reference trajectory."""
    if reference_dt <= 0 or not timesteps or min(timesteps) <= 0:
        raise ValueError("all timesteps must be positive")
    base = scenario or Scenario(
        duration=30.0,
        dt=reference_dt,
        disturbance_at=8.0,
        feed_composition_after=0.62,
    )
    runner = ScenarioRunner()
    reference = runner.run(replace(base, dt=reference_dt))
    reference_top = float(reference["x_top"].iloc[-1])
    reference_bottom = float(reference["x_bottom"].iloc[-1])
    cases: list[TimestepCase] = []
    for dt in timesteps:
        frame = runner.run(replace(base, dt=dt))
        cases.append(
            TimestepCase(
                dt=dt,
                samples=len(frame),
                final_top_absolute_difference=abs(
                    float(frame["x_top"].iloc[-1]) - reference_top
                ),
                final_bottom_absolute_difference=abs(
                    float(frame["x_bottom"].iloc[-1]) - reference_bottom
                ),
            )
        )
    return tuple(cases)


def benchmark_fault_detection(
    scenario: Scenario | None = None,
) -> FaultDetectionMetrics:
    """Measure EWMA behavior for a persistent, known analyzer-bias injection."""
    case = scenario or Scenario(
        duration=30.0,
        dt=0.1,
        disturbance_at=10.0,
        top_sensor_bias_after=0.05,
    )
    if case.top_sensor_bias_after == 0.0:
        raise ValueError("fault benchmark requires a nonzero sensor bias")
    frame = ScenarioRunner().run(case)
    before = frame.loc[frame["time"] < case.disturbance_at, "sensor_alarm"]
    after = frame.loc[frame["time"] >= case.disturbance_at]
    alarms_after = after.loc[after["sensor_alarm"], "time"]
    detected = not alarms_after.empty
    detection_delay = (
        float(alarms_after.iloc[0] - case.disturbance_at)
        if detected
        else float(case.duration - case.disturbance_at)
    )
    return FaultDetectionMetrics(
        injected_bias=case.top_sensor_bias_after,
        detection_delay=detection_delay,
        false_alarm_fraction=float(before.mean()) if len(before) else 0.0,
        post_fault_alarm_fraction=float(after["sensor_alarm"].mean()),
        detected=detected,
    )


def _process_context_frame(
    runner: ScenarioRunner,
    cases: tuple[Scenario, ...],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for scenario_id, case in enumerate(cases):
        frame = runner.run(case)
        post_disturbance = frame.loc[frame["time"] >= case.disturbance_at].copy()
        post_disturbance["scenario_id"] = scenario_id
        frames.append(post_disturbance)
    return pd.concat(frames, ignore_index=True)


def benchmark_soft_sensor() -> SoftSensorMetrics:
    """Evaluate the ridge sensor on complete operating scenarios held out from fitting."""
    training_cases = tuple(
        Scenario(
            duration=28.0,
            dt=0.2,
            disturbance_at=5.0,
            feed_composition_after=feed_composition,
            feed_rate_after=feed_rate,
        )
        for feed_composition in (0.38, 0.46, 0.54, 0.62, 0.70)
        for feed_rate in (0.80, 1.00, 1.20)
    )
    holdout_cases = tuple(
        Scenario(
            duration=28.0,
            dt=0.2,
            disturbance_at=5.0,
            feed_composition_after=feed_composition,
            feed_rate_after=feed_rate,
        )
        for feed_composition, feed_rate in (
            (0.42, 0.90),
            (0.50, 1.10),
            (0.58, 0.85),
            (0.66, 1.15),
        )
    )
    runner = ScenarioRunner()
    training = _process_context_frame(runner, training_cases)
    holdout = _process_context_frame(runner, holdout_cases)
    training_features = training.loc[:, SOFT_SENSOR_FEATURES].to_numpy(
        dtype=float, copy=True
    )
    holdout_features = holdout.loc[:, SOFT_SENSOR_FEATURES].to_numpy(
        dtype=float, copy=True
    )

    temperature_noise_std_c = 0.15
    random = np.random.default_rng(491)
    temperature_feature_count = 3
    training_features[:, :temperature_feature_count] += random.normal(
        0.0,
        temperature_noise_std_c,
        size=(len(training_features), temperature_feature_count),
    )
    holdout_features[:, :temperature_feature_count] += random.normal(
        0.0,
        temperature_noise_std_c,
        size=(len(holdout_features), temperature_feature_count),
    )
    training_target = training["x_top"].to_numpy(dtype=float)
    holdout_target = holdout["x_top"].to_numpy(dtype=float)
    sensor = RidgeSoftSensor(regularization=1e-2).fit(training_features, training_target)
    predictions = sensor.predict(holdout_features)
    errors = predictions - holdout_target
    rmse = float(np.sqrt(np.mean(errors**2)))
    constant_errors = float(training_target.mean()) - holdout_target
    constant_baseline_rmse = float(np.sqrt(np.mean(constant_errors**2)))
    return SoftSensorMetrics(
        training_scenarios=len(training_cases),
        holdout_scenarios=len(holdout_cases),
        training_samples=len(training),
        holdout_samples=len(holdout),
        temperature_noise_std_c=temperature_noise_std_c,
        rmse=rmse,
        mae=float(np.mean(np.abs(errors))),
        constant_baseline_rmse=constant_baseline_rmse,
        rmse_improvement_fraction=1.0 - rmse / constant_baseline_rmse,
    )


def _fault_scenario(
    fault: str,
    *,
    seed: int,
    noise_std: float,
) -> Scenario:
    baseline = Scenario(
        duration=35.0,
        dt=0.1,
        disturbance_at=10.0,
        feed_composition_after=0.50,
        top_sensor_noise_std=noise_std,
        random_seed=seed,
    )
    if fault == "positive analyzer bias":
        return replace(baseline, top_sensor_bias_after=0.03)
    if fault == "negative analyzer bias":
        return replace(baseline, top_sensor_bias_after=-0.03)
    if fault == "positive analyzer drift":
        return replace(baseline, top_sensor_drift_rate_after=0.003)
    raise ValueError(f"unknown fault family: {fault}")


def _summarize_fault_case(
    runner: ScenarioRunner,
    *,
    fault: str,
    magnitude: float,
    units: str,
    replicates: int,
    noise_std: float,
) -> FaultCaseMetrics:
    detections = 0
    delays: list[float] = []
    pre_fault_alarms = 0
    pre_fault_samples = 0
    post_fault_alarms = 0
    post_fault_samples = 0
    for seed in range(replicates):
        case = _fault_scenario(fault, seed=seed, noise_std=noise_std)
        frame = runner.run(case)
        before = frame.loc[frame["time"] < case.disturbance_at, "sensor_alarm"]
        after = frame.loc[frame["time"] >= case.disturbance_at]
        alarms_after = after.loc[after["sensor_alarm"], "time"]
        detected = not alarms_after.empty
        detections += int(detected)
        delays.append(
            float(alarms_after.iloc[0] - case.disturbance_at)
            if detected
            else case.duration - case.disturbance_at
        )
        pre_fault_alarms += int(before.sum())
        pre_fault_samples += len(before)
        post_fault_alarms += int(after["sensor_alarm"].sum())
        post_fault_samples += len(after)
    return FaultCaseMetrics(
        fault=fault,
        magnitude=magnitude,
        units=units,
        replicates=replicates,
        detection_rate=detections / replicates,
        median_detection_delay=float(np.median(delays)),
        p95_detection_delay=float(np.percentile(delays, 95)),
        pre_fault_false_alarm_fraction=pre_fault_alarms / pre_fault_samples,
        post_fault_alarm_fraction=post_fault_alarms / post_fault_samples,
    )


def benchmark_fault_suite(
    *,
    replicates: int = 12,
    noise_std: float = 0.004,
) -> FaultSuiteMetrics:
    """Stress the EWMA monitor across seeded noise, bias direction, and gradual drift."""
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if noise_std < 0:
        raise ValueError("noise_std must be nonnegative")
    runner = ScenarioRunner()
    no_fault_alarms = 0
    no_fault_samples = 0
    for seed in range(replicates):
        baseline = runner.run(
            Scenario(
                duration=35.0,
                dt=0.1,
                disturbance_at=10.0,
                feed_composition_after=0.50,
                top_sensor_noise_std=noise_std,
                random_seed=seed,
            )
        )
        no_fault_alarms += int(baseline["sensor_alarm"].sum())
        no_fault_samples += len(baseline)

    definitions = (
        ("positive analyzer bias", 0.03, "mole fraction"),
        ("negative analyzer bias", -0.03, "mole fraction"),
        ("positive analyzer drift", 0.003, "mole fraction/min"),
    )
    cases = tuple(
        _summarize_fault_case(
            runner,
            fault=fault,
            magnitude=magnitude,
            units=units,
            replicates=replicates,
            noise_std=noise_std,
        )
        for fault, magnitude, units in definitions
    )
    return FaultSuiteMetrics(
        noise_standard_deviation=noise_std,
        no_fault_alarm_fraction=no_fault_alarms / no_fault_samples,
        cases=cases,
    )


def generate_validation_report() -> ValidationReport:
    """Run the complete deterministic validation suite."""
    reference_dt = 0.05
    return ValidationReport(
        physics=validate_physics(),
        control=benchmark_control(),
        timestep_reference_dt=reference_dt,
        timestep_cases=benchmark_timesteps(reference_dt=reference_dt),
        fault_detection=benchmark_fault_detection(),
        soft_sensor=benchmark_soft_sensor(),
        fault_suite=benchmark_fault_suite(),
    )


def render_markdown(report: ValidationReport) -> str:
    """Render a concise recruiter- and reviewer-readable validation report."""
    physics = report.physics
    fault = report.fault_detection
    soft_sensor = report.soft_sensor
    control_rows = "\n".join(
        f"| {mode} | {variable} | {metrics.iae:.6f} | {metrics.ise:.6f} | "
        f"{metrics.peak_absolute_error:.6f} | {metrics.final_absolute_error:.6f} | "
        f"{metrics.settling_time:.2f} |"
        for mode, variable, metrics in (
            ("open loop", "top composition", report.control.open_loop_top),
            ("paired PID", "top composition", report.control.closed_loop_top),
            ("open loop", "bottom composition", report.control.open_loop_bottom),
            ("paired PID", "bottom composition", report.control.closed_loop_bottom),
        )
    )
    timestep_rows = "\n".join(
        f"| {case.dt:.3f} | {case.samples} | "
        f"{case.final_top_absolute_difference:.3e} | "
        f"{case.final_bottom_absolute_difference:.3e} |"
        for case in report.timestep_cases
    )
    fault_suite_rows = "\n".join(
        f"| {case.fault} | {case.magnitude:+.3f} {case.units} | "
        f"{case.detection_rate:.1%} | {case.median_detection_delay:.3f} | "
        f"{case.p95_detection_delay:.3f} | "
        f"{case.pre_fault_false_alarm_fraction:.3%} | "
        f"{case.post_fault_alarm_fraction:.3%} |"
        for case in report.fault_suite.cases
    )
    return f"""# DistillTwin validation report

> Scope: Aspen-independent verification of the transparent reduced-order model.
> These results do not claim agreement with Aspen or plant data.

## Physics and steady state

| Check | Result |
|---|---:|
| Absolute light-key balance residual | {physics.material_balance_absolute_residual:.3e} |
| Maximum nominal steady-state derivative | {physics.steady_state_max_derivative:.3e} |
| Minimum steady-state composition | {physics.steady_state_min_composition:.5f} |
| Maximum steady-state composition | {physics.steady_state_max_composition:.5f} |
| Monotonic composition profile | {physics.steady_state_monotonic} |

## Disturbance-rejection benchmark

The benchmark applies the same feed light-key step from 0.50 to 0.62 to fixed-input
open-loop operation and to the paired composition PID loops.

| Mode | Variable | IAE | ISE | Peak error | Final error | Settling time |
|---|---|---:|---:|---:|---:|---:|
{control_rows}

## RK4 timestep sensitivity

Final-product differences are measured against a dt =
{report.timestep_reference_dt:.3f} min reference.

| dt (min) | Samples | Final top difference | Final bottom difference |
|---:|---:|---:|---:|
{timestep_rows}

## Fault-detection benchmark

| Metric | Result |
|---|---:|
| Injected top-analyzer bias | {fault.injected_bias:.3f} |
| Detected | {fault.detected} |
| Detection delay (min) | {fault.detection_delay:.3f} |
| Pre-fault false-alarm fraction | {fault.false_alarm_fraction:.3%} |
| Post-fault alarm fraction | {fault.post_fault_alarm_fraction:.3%} |

## Soft-sensor scenario holdout

The ridge soft sensor is fitted on complete operating scenarios and evaluated on
separate feed-composition/feed-rate combinations. The three selected tray-temperature
features include deterministic Gaussian noise with a
`{soft_sensor.temperature_noise_std_c:.2f} degC` standard deviation. The directly
invertible top-temperature proxy is excluded from the features.

| Metric | Result |
|---|---:|
| Training scenarios | {soft_sensor.training_scenarios} |
| Holdout scenarios | {soft_sensor.holdout_scenarios} |
| Holdout samples | {soft_sensor.holdout_samples} |
| Holdout RMSE | {soft_sensor.rmse:.6f} |
| Holdout MAE | {soft_sensor.mae:.6f} |
| Constant-baseline RMSE | {soft_sensor.constant_baseline_rmse:.6f} |
| RMSE improvement over constant baseline | {soft_sensor.rmse_improvement_fraction:.1%} |

## Noisy multi-run fault benchmark

Each fault is repeated across {report.fault_suite.cases[0].replicates} seeded noise
realizations with analyzer noise standard deviation
`{report.fault_suite.noise_standard_deviation:.3f}`. An additional no-fault baseline
produced an alarm fraction of `{report.fault_suite.no_fault_alarm_fraction:.3%}`.

| Fault | Magnitude | Detect | Median delay | P95 delay | Pre-fault alarms | Post-fault alarms |
|---|---:|---:|---:|---:|---:|---:|
{fault_suite_rows}

Generated deterministically by `distilltwin-validate`.
"""


def write_validation_bundle(
    output_directory: str | Path = "validation-report",
    report: ValidationReport | None = None,
) -> tuple[Path, Path]:
    """Write Markdown and JSON evidence plus tabular CSV data."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    result = report or generate_validation_report()
    markdown_path = output / "VALIDATION_REPORT.md"
    json_path = output / "validation_report.json"
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(result.control.rows()).to_csv(output / "control_benchmark.csv", index=False)
    pd.DataFrame([case.to_dict() for case in result.timestep_cases]).to_csv(
        output / "timestep_sensitivity.csv",
        index=False,
    )
    pd.DataFrame([case.to_dict() for case in result.fault_suite.cases]).to_csv(
        output / "fault_suite.csv",
        index=False,
    )
    return markdown_path, json_path


def main() -> None:
    """Generate a validation bundle from the command line."""
    parser = argparse.ArgumentParser(
        description="Generate reproducible Aspen-independent validation evidence."
    )
    parser.add_argument(
        "--output",
        default="validation-report",
        help="Directory for Markdown, JSON, and CSV results.",
    )
    args = parser.parse_args()
    report = generate_validation_report()
    markdown_path, json_path = write_validation_bundle(args.output, report)
    print(render_markdown(report))
    print(f"Wrote {markdown_path} and {json_path}")


if __name__ == "__main__":
    main()
