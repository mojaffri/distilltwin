import json
from pathlib import Path

import pandas as pd
import pytest

from distilltwin.scenarios import Scenario
from distilltwin.validation import (
    benchmark_control,
    benchmark_fault_detection,
    benchmark_timesteps,
    generate_validation_report,
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
    assert max(top_differences) < 5e-4
    assert max(bottom_differences) < 5e-4
    assert top_differences[-1] < 5e-5
    assert bottom_differences[-1] < 5e-5


def test_known_sensor_bias_is_detected_without_false_alarms() -> None:
    metrics = benchmark_fault_detection()
    assert metrics.detected
    assert metrics.detection_delay <= 0.5
    assert metrics.false_alarm_fraction == pytest.approx(0.0)
    assert metrics.post_fault_alarm_fraction > 0.95


def test_validation_bundle_is_machine_and_human_readable(tmp_path: Path) -> None:
    report = generate_validation_report()
    markdown_path, json_path = write_validation_bundle(tmp_path / "evidence", report)
    assert "Aspen-independent" in markdown_path.read_text(encoding="utf-8")
    json_text = json_path.read_text(encoding="utf-8")
    assert '"material_balance_absolute_residual"' in json_text
    assert '"state_estimation"' in json_text
    assert (markdown_path.parent / "control_benchmark.csv").exists()
    assert (markdown_path.parent / "timestep_sensitivity.csv").exists()
    assert (markdown_path.parent / "state_estimation_benchmark.csv").exists()

    estimation = report.state_estimation
    assert estimation.state_dimension == 8
    assert estimation.measured_signal_count == 4
    assert all(case.observability_rank == 8 for case in estimation.cases)
    cases = {case.scenario.name: case.metrics for case in estimation.cases}
    assert cases["sensor noise"].post_disturbance_rmse > cases["nominal"].post_disturbance_rmse
    assert cases["model mismatch"].overall_rmse > cases["nominal"].overall_rmse
    assert not cases["unmeasured feed composition step"].converged

    reference = Path(__file__).parents[1] / "docs" / "reference"
    assert markdown_path.read_text(encoding="utf-8") == (
        reference / "VALIDATION_REPORT.md"
    ).read_text(encoding="utf-8")
    generated_json = json.loads(json_path.read_text(encoding="utf-8"))
    reference_json = json.loads(
        (reference / "validation_report.json").read_text(encoding="utf-8")
    )
    _assert_nested_results_close(generated_json, reference_json)
    for filename in (
        "control_benchmark.csv",
        "timestep_sensitivity.csv",
        "state_estimation_benchmark.csv",
    ):
        pd.testing.assert_frame_equal(
            pd.read_csv(markdown_path.parent / filename),
            pd.read_csv(reference / filename),
            check_exact=False,
            rtol=1e-10,
            atol=1e-12,
        )


def _assert_nested_results_close(actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key, value in expected.items():
            _assert_nested_results_close(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            _assert_nested_results_close(actual_item, expected_item)
    elif isinstance(expected, float):
        assert isinstance(actual, (float, int))
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-12)
    else:
        assert actual == expected
