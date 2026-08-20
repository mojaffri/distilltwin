"""Control-oriented dynamic model of a binary distillation column.

The model applies component balances to equilibrium stages under constant molar
overflow. It is intended for control, fault, and numerical experiments within the
assumptions documented in the repository. Aspen and plant-data comparisons are
tracked separately.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ColumnConfig:
    """Physical and numerical configuration for the staged column."""

    n_stages: int = 8
    feed_stage: int = 4
    relative_volatility: float = 2.4
    tray_holdup: float = 5.0
    condenser_holdup: float = 8.0
    reboiler_holdup: float = 8.0
    nominal_feed: float = 1.0
    nominal_feed_composition: float = 0.50
    nominal_reflux: float = 2.50
    nominal_boilup: float = 3.00

    def __post_init__(self) -> None:
        if self.n_stages < 4:
            raise ValueError("n_stages must include at least four equilibrium stages")
        if not 1 <= self.feed_stage <= self.n_stages - 2:
            raise ValueError("feed_stage must be an interior stage")

        numeric_values = np.array(
            [
                self.relative_volatility,
                self.tray_holdup,
                self.condenser_holdup,
                self.reboiler_holdup,
                self.nominal_feed,
                self.nominal_feed_composition,
                self.nominal_reflux,
                self.nominal_boilup,
            ],
            dtype=float,
        )
        if not np.isfinite(numeric_values).all():
            raise ValueError("column configuration values must be finite")
        if self.relative_volatility <= 1.0:
            raise ValueError("relative_volatility must exceed one for the light key")
        if min(self.tray_holdup, self.condenser_holdup, self.reboiler_holdup) <= 0:
            raise ValueError("stage holdups must be positive")
        if self.nominal_feed <= 0 or self.nominal_reflux <= 0 or self.nominal_boilup <= 0:
            raise ValueError("nominal flows must be positive")
        if not 0.0 <= self.nominal_feed_composition <= 1.0:
            raise ValueError("nominal_feed_composition must be between zero and one")
        distillate = self.nominal_boilup - self.nominal_reflux
        bottoms = self.nominal_reflux + self.nominal_feed - self.nominal_boilup
        if distillate <= 0 or bottoms <= 0:
            raise ValueError("nominal flows must produce positive distillate and bottoms products")


@dataclass(frozen=True)
class ColumnInputs:
    """Column flows and feed condition in consistent molar units."""

    feed_rate: float
    feed_composition: float
    reflux_flow: float
    boilup_flow: float

    def validate(self) -> None:
        values = np.array(
            [self.feed_rate, self.feed_composition, self.reflux_flow, self.boilup_flow],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("column inputs must be finite")
        if self.feed_rate <= 0 or self.reflux_flow <= 0 or self.boilup_flow <= 0:
            raise ValueError("all flows must be positive")
        if not 0.0 <= self.feed_composition <= 1.0:
            raise ValueError("feed_composition must be between zero and one")
        distillate = self.boilup_flow - self.reflux_flow
        bottoms = self.reflux_flow + self.feed_rate - self.boilup_flow
        if distillate <= 0 or bottoms <= 0:
            raise ValueError("flows must produce positive distillate and bottoms products")


class DistillationColumn:
    """Dynamic binary column with a total condenser and partial reboiler."""

    def __init__(self, config: ColumnConfig | None = None) -> None:
        self.config = config or ColumnConfig()

    @property
    def nominal_inputs(self) -> ColumnInputs:
        cfg = self.config
        return ColumnInputs(
            feed_rate=cfg.nominal_feed,
            feed_composition=cfg.nominal_feed_composition,
            reflux_flow=cfg.nominal_reflux,
            boilup_flow=cfg.nominal_boilup,
        )

    def _coerce_state(self, state: FloatArray, *, require_physical: bool) -> FloatArray:
        x = np.asarray(state, dtype=float)
        if x.shape != (self.config.n_stages,):
            raise ValueError(f"state must have shape ({self.config.n_stages},)")
        if not np.isfinite(x).all():
            raise ValueError("state must contain only finite compositions")
        if require_physical and np.any((x < 0.0) | (x > 1.0)):
            raise ValueError("state compositions must be between zero and one")
        return x.astype(np.float64, copy=False)

    def equilibrium_vapor(self, liquid_composition: FloatArray) -> FloatArray:
        """Return vapor composition from a constant-relative-volatility VLE relation."""
        alpha = self.config.relative_volatility
        x = np.asarray(liquid_composition, dtype=float)
        if not np.isfinite(x).all():
            raise ValueError("liquid composition must contain only finite values")
        if np.any((x < 0.0) | (x > 1.0)):
            raise ValueError("liquid composition must be between zero and one")
        return (alpha * x / (1.0 + (alpha - 1.0) * x)).astype(np.float64)

    def temperature_proxy(self, liquid_composition: FloatArray) -> FloatArray:
        """Map composition to an illustrative normal-boiling temperature signal in Celsius."""
        x = np.asarray(liquid_composition, dtype=float)
        if not np.isfinite(x).all():
            raise ValueError("liquid composition must contain only finite values")
        if np.any((x < 0.0) | (x > 1.0)):
            raise ValueError("liquid composition must be between zero and one")
        return (110.6 - 30.5 * x).astype(np.float64)

    def derivatives(self, state: FloatArray, inputs: ColumnInputs) -> FloatArray:
        """Evaluate stage light-key component balances."""
        inputs.validate()
        cfg = self.config
        x = self._coerce_state(state, require_physical=False)
        y = cfg.relative_volatility * x / (1.0 + (cfg.relative_volatility - 1.0) * x)
        if not np.isfinite(y).all():
            raise ValueError("VLE evaluation produced a non-finite intermediate state")

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
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be a finite positive value")
        x = self._coerce_state(state, require_physical=True)
        k1 = self.derivatives(x, inputs)
        k2 = self.derivatives(x + 0.5 * dt * k1, inputs)
        k3 = self.derivatives(x + 0.5 * dt * k2, inputs)
        k4 = self.derivatives(x + dt * k3, inputs)
        next_state = x + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        if not np.isfinite(next_state).all():
            raise RuntimeError("integration produced a non-finite state")
        return np.clip(next_state, 0.0, 1.0).astype(np.float64)

    def steady_state(
        self,
        inputs: ColumnInputs | None = None,
        *,
        tolerance: float = 1e-9,
        max_steps: int = 50_000,
    ) -> FloatArray:
        """Numerically settle the column at fixed inputs."""
        if not np.isfinite(tolerance) or tolerance <= 0:
            raise ValueError("tolerance must be a finite positive value")
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        fixed_inputs = inputs or self.nominal_inputs
        fixed_inputs.validate()
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
        if not np.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be a finite positive value")
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be a finite positive value")
        state = (
            self.steady_state()
            if initial_state is None
            else self._coerce_state(initial_state, require_physical=True)
        )
        records: list[dict[str, float]] = []
        for time in np.arange(0.0, duration + dt / 2.0, dt):
            inputs = input_schedule(float(time))
            inputs.validate()
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
