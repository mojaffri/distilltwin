from pathlib import Path

import pytest

from distilltwin.scenarios import Scenario
from distilltwin.validation import (
    benchmark_control,
    benchmark_fault_detection,
    benchmark_timesteps,
    validate_physics,
    write_validation_bundle,
)


def test_physics_validation_closes_balances_and_is_stationary() -> None:
    result = validate_physics()
    assert result.material_balance_absolute_residual < 1e-12
    assert result.steady_state_max_derivative < 3e-8
    assert 0.0 < result.steady_state_min_composition
    assert result.steady_state_max_composition < 1.0
    assert result.steady_state_monotonic


def test_pid_improves_final_disturbance_rejection() -> None:
    benchmark = benchmark_control(
        Scenario(
            duration=40.0,
            dt=0.2,
            disturbance_at=10.0,
            feed_composition_after=0.62,
        )
    )
    assert (
        benchmark.closed_loop_top.final_absolute_error
        < benchmark.open_loop_top.final_absolute_error
    )
    assert (
        benchmark.closed_loop_bottom.final_absolute_error
        < benchmark.open_loop_bottom.final_absolute_error
    )
    assert benchmark.closed_loop_top.iae < benchmark.open_loop_top.iae


def test_timestep_study_converges_toward_fine_reference() -> None:
    cases = benchmark_timesteps(
        Scenario(
            duration=20.0,
            dt=0.05,
            disturbance_at=5.0,
            feed_composition_after=0.60,
        ),
        timesteps=(0.4, 0.2, 0.1),
        reference_dt=0.05,
    )
    top_differences = [case.final_top_absolute_difference for case in cases]
    bottom_differences = [case.final_bottom_absolute_difference for case in cases]
    assert top_differences[-1] < top_differences[0]
    assert bottom_differences[-1] < bottom_differences[0]
    assert top_differences[-1] < 5e-4
    assert bottom_differences[-1] < 5e-4


def test_known_sensor_bias_is_detected_without_false_alarms() -> None:
    metrics = benchmark_fault_detection()
    assert metrics.detected
    assert metrics.detection_delay <= 0.5
    assert metrics.false_alarm_fraction == pytest.approx(0.0)
    assert metrics.post_fault_alarm_fraction > 0.95


def test_validation_bundle_is_machine_and_human_readable(tmp_path: Path) -> None:
    markdown_path, json_path = write_validation_bundle(tmp_path / "evidence")
    assert "Aspen-independent" in markdown_path.read_text(encoding="utf-8")
    assert '"material_balance_absolute_residual"' in json_path.read_text(
        encoding="utf-8"
    )
    assert (markdown_path.parent / "control_benchmark.csv").exists()
    assert (markdown_path.parent / "timestep_sensitivity.csv").exists()
