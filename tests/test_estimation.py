import numpy as np
import pytest

from distilltwin.estimation import (
    ExtendedKalmanFilter,
    MeasurementConfig,
    MeasurementModel,
    discrete_transition_jacobian,
    local_observability_rank,
)
from distilltwin.estimation_validation import EstimationScenario, run_estimation_case
from distilltwin.model import DistillationColumn


def test_measurement_model_uses_only_the_configured_stage_signals() -> None:
    column = DistillationColumn()
    config = MeasurementConfig(
        composition_stages=(7, 0),
        temperature_stages=(3,),
        composition_noise_std=0.001,
        temperature_noise_std=0.1,
    )
    model = MeasurementModel(column, config)
    state = column.steady_state()

    observed = model.observe(state)
    jacobian = model.jacobian()

    assert observed.shape == (3,)
    assert observed[0] == pytest.approx(state[7])
    assert observed[1] == pytest.approx(state[0])
    assert observed[2] == pytest.approx(column.temperature_proxy(state)[3])
    assert np.flatnonzero(jacobian[0]).tolist() == [7]
    assert np.flatnonzero(jacobian[1]).tolist() == [0]
    assert np.flatnonzero(jacobian[2]).tolist() == [3]


def test_local_linearization_is_observable_with_four_default_signals() -> None:
    column = DistillationColumn()
    measurements = MeasurementModel(column)
    rank = local_observability_rank(
        column,
        measurements,
        column.steady_state(),
        column.nominal_inputs,
        0.2,
    )
    assert measurements.size == 4
    assert rank == column.config.n_stages


def test_rk4_analytical_jacobian_matches_a_finite_difference_check() -> None:
    column = DistillationColumn()
    state = column.steady_state()
    analytical = discrete_transition_jacobian(
        column, state, column.nominal_inputs, 0.2
    )
    numerical = np.empty_like(analytical)
    step = 1e-6
    for stage in range(column.config.n_stages):
        lower = state.copy()
        upper = state.copy()
        lower[stage] -= step
        upper[stage] += step
        numerical[:, stage] = (
            column.step(upper, column.nominal_inputs, 0.2)
            - column.step(lower, column.nominal_inputs, 0.2)
        ) / (2.0 * step)
    assert np.allclose(analytical, numerical, rtol=2e-6, atol=2e-8)


def test_ekf_reconstructs_hidden_states_and_preserves_covariance() -> None:
    column = DistillationColumn()
    true_state = column.steady_state()
    initial = np.clip(
        true_state + np.linspace(0.04, -0.04, column.config.n_stages),
        0.0,
        1.0,
    )
    measurements = MeasurementModel(column)
    estimator = ExtendedKalmanFilter(
        column,
        measurements,
        initial_state=initial,
    )
    initial_error = float(np.sqrt(np.mean((initial - true_state) ** 2)))

    for _ in range(30):
        estimator.correct(measurements.observe(true_state))
        true_state = column.step(true_state, column.nominal_inputs, 0.2)
        estimator.predict(column.nominal_inputs, 0.2)

    final_error = float(np.sqrt(np.mean((estimator.state - true_state) ** 2)))
    eigenvalues = np.linalg.eigvalsh(estimator.covariance)
    assert final_error < initial_error / 10.0
    assert np.allclose(estimator.covariance, estimator.covariance.T)
    assert np.all(eigenvalues > 0.0)


def test_estimation_case_is_reproducible_with_noise_and_mismatch() -> None:
    scenario = EstimationScenario(
        name="regression",
        duration=6.0,
        dt=0.2,
        disturbance_at=2.0,
        feed_composition_after=0.60,
        measurement_noise_scale=2.0,
        plant_relative_volatility=2.25,
        plant_holdup_scale=1.10,
        estimator_knows_feed_composition=False,
        random_seed=17,
    )
    first, first_frame = run_estimation_case(scenario)
    second, second_frame = run_estimation_case(scenario)

    assert first.to_dict() == second.to_dict()
    assert first_frame.equals(second_frame)
    assert first.observability_rank == 8
    assert np.isfinite(first.metrics.overall_rmse)
    assert len(first.metrics.per_stage_rmse) == 8


def test_estimator_rejects_invalid_measurements_and_configuration() -> None:
    column = DistillationColumn()
    with pytest.raises(ValueError, match="at least one"):
        MeasurementConfig(composition_stages=(), temperature_stages=())
    with pytest.raises(ValueError, match="exceeds"):
        MeasurementModel(column, MeasurementConfig(composition_stages=(8,)))

    estimator = ExtendedKalmanFilter(column, MeasurementModel(column))
    with pytest.raises(ValueError, match="shape"):
        estimator.correct(np.zeros(2))
    with pytest.raises(ValueError, match="finite"):
        estimator.correct(np.full(4, np.nan))
