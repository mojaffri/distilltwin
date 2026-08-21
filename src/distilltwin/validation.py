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

from distilltwin.estimation_validation import (
    EstimationBenchmark,
    benchmark_state_estimator,
)
from distilltwin.model import ColumnInputs, DistillationColumn
from distilltwin.scenarios import Scenario, ScenarioRunner


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
class ValidationReport:
    """Complete deterministic validation result."""

    physics: PhysicsValidation
    control: ControlBenchmark
    timestep_reference_dt: float
    timestep_cases: tuple[TimestepCase, ...]
    fault_detection: FaultDetectionMetrics
    state_estimation: EstimationBenchmark

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
            "state_estimation": self.state_estimation.to_dict(),
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


def generate_validation_report() -> ValidationReport:
    """Run the complete deterministic validation suite."""
    reference_dt = 0.05
    return ValidationReport(
        physics=validate_physics(),
        control=benchmark_control(),
        timestep_reference_dt=reference_dt,
        timestep_cases=benchmark_timesteps(reference_dt=reference_dt),
        fault_detection=benchmark_fault_detection(),
        state_estimation=benchmark_state_estimator(),
    )


def render_markdown(report: ValidationReport) -> str:
    """Render a concise human-readable validation report."""
    physics = report.physics
    fault = report.fault_detection
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
    estimation_rows = "\n".join(
        f"| {case.scenario.name} | {case.observability_rank} | "
        f"{case.metrics.overall_rmse:.6f} | "
        f"{case.metrics.post_disturbance_rmse:.6f} | "
        f"{case.metrics.transient_rmse:.6f} | "
        f"{case.metrics.peak_state_rmse:.6f} | "
        f"{case.metrics.convergence_delay:.2f} | {case.metrics.converged} |"
        for case in report.state_estimation.cases
    )
    estimation_header = (
        "| Scenario | Obs. rank | Overall RMSE | Post-step RMSE | Transient RMSE | "
        "Peak state RMSE | Convergence delay | Converged |"
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

## Extended Kalman filter state estimation

The estimator reconstructs {report.state_estimation.state_dimension} stage compositions
from {report.state_estimation.measured_signal_count} signals: product compositions on
stages {report.state_estimation.composition_stages} and temperature proxies on stages
{report.state_estimation.temperature_stages}. The model-mismatch case uses a hidden plant
with relative volatility 2.20 and holdups 15% above the estimator model.

{estimation_header}
|---|---:|---:|---:|---:|---:|---:|---:|
{estimation_rows}

## Fault-detection benchmark

| Metric | Result |
|---|---:|
| Injected top-analyzer bias | {fault.injected_bias:.3f} |
| Detected | {fault.detected} |
| Detection delay (min) | {fault.detection_delay:.3f} |
| Pre-fault false-alarm fraction | {fault.false_alarm_fraction:.3%} |
| Post-fault alarm fraction | {fault.post_fault_alarm_fraction:.3%} |

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
    pd.DataFrame(result.state_estimation.rows()).to_csv(
        output / "state_estimation_benchmark.csv",
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
