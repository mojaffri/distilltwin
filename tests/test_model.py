import numpy as np
import pytest

from distilltwin.model import ColumnConfig, ColumnInputs, DistillationColumn


def test_vle_is_bounded_and_enriches_light_key() -> None:
    column = DistillationColumn()
    liquid = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
    vapor = column.equilibrium_vapor(liquid)
    assert np.all((0.0 <= vapor) & (vapor <= 1.0))
    assert np.all(vapor[1:-1] > liquid[1:-1])


def test_component_balance_closes() -> None:
    column = DistillationColumn()
    state = np.linspace(0.1, 0.9, column.config.n_stages)
    inputs = column.nominal_inputs
    rates = column.derivatives(state, inputs)
    holdups = np.full(column.config.n_stages, column.config.tray_holdup)
    holdups[0] = column.config.reboiler_holdup
    holdups[-1] = column.config.condenser_holdup
    accumulation = float(rates @ holdups)
    distillate = inputs.boilup_flow - inputs.reflux_flow
    bottoms = inputs.reflux_flow + inputs.feed_rate - inputs.boilup_flow
    boundary_flux = (
        inputs.feed_rate * inputs.feed_composition
        - distillate * state[-1]
        - bottoms * state[0]
    )
    assert accumulation == pytest.approx(boundary_flux)


def test_nominal_steady_state_is_ordered_and_stationary() -> None:
    column = DistillationColumn()
    state = column.steady_state()
    assert np.all(np.diff(state) > 0)
    assert float(np.max(np.abs(column.derivatives(state, column.nominal_inputs)))) < 3e-8


def test_invalid_product_flows_are_rejected() -> None:
    bad = ColumnInputs(1.0, 0.5, reflux_flow=2.5, boilup_flow=3.6)
    with pytest.raises(ValueError, match="positive distillate and bottoms"):
        bad.validate()


def test_configuration_requires_interior_feed_stage() -> None:
    with pytest.raises(ValueError, match="interior"):
        ColumnConfig(feed_stage=0)


def test_nonfinite_inputs_and_nonphysical_states_are_rejected() -> None:
    column = DistillationColumn()
    with pytest.raises(ValueError, match="finite"):
        column.derivatives(
            np.linspace(0.1, 0.9, column.config.n_stages),
            ColumnInputs(np.nan, 0.5, 2.5, 3.0),
        )
    with pytest.raises(ValueError, match="between zero and one"):
        column.step(np.full(column.config.n_stages, 1.1), column.nominal_inputs, 0.1)
    with pytest.raises(ValueError, match="finite and positive"):
        column.step(column.steady_state(), column.nominal_inputs, np.nan)


def test_unstable_timestep_is_not_hidden_by_state_clipping() -> None:
    column = DistillationColumn()
    with pytest.raises((ValueError, FloatingPointError)):
        column.step(
            np.linspace(0.1, 0.9, column.config.n_stages),
            column.nominal_inputs,
            10.0,
        )

