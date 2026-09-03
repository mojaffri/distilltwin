"""Closed-loop disturbance and fault scenarios."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from distilltwin.analytics import EWMAResidualMonitor
from distilltwin.control import PIDConfig, PIDController
from distilltwin.model import ColumnInputs, DistillationColumn


@dataclass(frozen=True)
class Scenario:
    """Configuration for a reproducible closed-loop experiment."""

    duration: float = 60.0
    dt: float = 0.1
    disturbance_at: float = 20.0
    feed_composition_after: float = 0.58
    feed_rate_after: float = 1.0
    top_sensor_bias_after: float = 0.0
    top_sensor_drift_rate_after: float = 0.0
    top_sensor_noise_std: float = 0.0
    reflux_effectiveness_after: float = 1.0
    random_seed: int = 0

    def __post_init__(self) -> None:
        if self.duration <= 0 or self.dt <= 0:
            raise ValueError("duration and dt must be positive")
        if not 0.0 <= self.disturbance_at <= self.duration:
            raise ValueError("disturbance_at must fall within the simulation")
        if not 0.0 <= self.feed_composition_after <= 1.0:
            raise ValueError("feed composition must be between zero and one")
        if self.feed_rate_after <= 0:
            raise ValueError("feed rate must be positive")
        if self.top_sensor_noise_std < 0:
            raise ValueError("sensor-noise standard deviation must be nonnegative")
        if not 0.5 <= self.reflux_effectiveness_after <= 1.0:
            raise ValueError("reflux effectiveness must be between 0.5 and 1.0")
        if self.random_seed < 0:
            raise ValueError("random_seed must be nonnegative")


def _project_boilup(commanded_boilup: float, reflux: float, feed_rate: float) -> float:
    """Keep both product flows positive without assuming a nominal feed rate."""
    margin = min(0.05, feed_rate / 4.0)
    lower = reflux + margin
    upper = reflux + feed_rate - margin
    return min(upper, max(lower, commanded_boilup))


class ScenarioRunner:
    """Run paired composition controllers around the dynamic column model."""

    def __init__(self, column: DistillationColumn | None = None) -> None:
        self.column = column or DistillationColumn()
        self._nominal_state = self.column.steady_state()

    def run(self, scenario: Scenario) -> pd.DataFrame:
        cfg = self.column.config
        state = self._nominal_state.copy()
        top_setpoint = float(state[-1])
        bottom_setpoint = float(state[0])
        random = np.random.default_rng(scenario.random_seed)
        lower_tray = max(1, cfg.n_stages // 3)
        upper_tray = min(cfg.n_stages - 2, 2 * cfg.n_stages // 3)

        top_controller = PIDController(
            PIDConfig(
                kp=4.0,
                ki=0.18,
                output_min=1.50,
                output_max=2.85,
                bias=cfg.nominal_reflux,
                action=1.0,
            )
        )
        bottom_controller = PIDController(
            PIDConfig(
                kp=3.0,
                ki=0.12,
                output_min=2.60,
                output_max=3.35,
                bias=cfg.nominal_boilup,
                action=-1.0,
            )
        )
        monitor = EWMAResidualMonitor()
        records: list[dict[str, float | bool]] = []

        for time in np.arange(0.0, scenario.duration + scenario.dt / 2.0, scenario.dt):
            disturbed = time >= scenario.disturbance_at
            feed_rate = scenario.feed_rate_after if disturbed else cfg.nominal_feed
            feed_composition = (
                scenario.feed_composition_after
                if disturbed
                else cfg.nominal_feed_composition
            )
            sensor_bias = scenario.top_sensor_bias_after if disturbed else 0.0
            sensor_drift = (
                scenario.top_sensor_drift_rate_after
                * max(0.0, float(time) - scenario.disturbance_at)
                if disturbed
                else 0.0
            )
            sensor_noise = (
                float(random.normal(0.0, scenario.top_sensor_noise_std))
                if scenario.top_sensor_noise_std
                else 0.0
            )
            effectiveness = scenario.reflux_effectiveness_after if disturbed else 1.0
            measured_top = float(
                np.clip(state[-1] + sensor_bias + sensor_drift + sensor_noise, 0.0, 1.0)
            )
            measured_bottom = float(state[0])

            commanded_reflux = top_controller.update(
                setpoint=top_setpoint,
                measurement=measured_top,
                dt=scenario.dt,
            )
            reflux = commanded_reflux * effectiveness
            commanded_boilup = bottom_controller.update(
                setpoint=bottom_setpoint,
                measurement=measured_bottom,
                dt=scenario.dt,
            )
            boilup = _project_boilup(commanded_boilup, reflux, feed_rate)

            inputs = ColumnInputs(feed_rate, feed_composition, reflux, boilup)
            temperatures = self.column.temperature_proxy(state)
            sensor_residual = measured_top - float(state[-1])
            ewma, alarm = monitor.update(sensor_residual)
            records.append(
                {
                    "time": float(time),
                    "x_bottom": float(state[0]),
                    "x_top": float(state[-1]),
                    "measured_top": measured_top,
                    "top_setpoint": top_setpoint,
                    "bottom_setpoint": bottom_setpoint,
                    "temperature_bottom": float(temperatures[0]),
                    "temperature_lower_tray": float(temperatures[lower_tray]),
                    "temperature_upper_tray": float(temperatures[upper_tray]),
                    "temperature_top": float(temperatures[-1]),
                    "feed_rate": feed_rate,
                    "feed_composition": feed_composition,
                    "reflux_command": commanded_reflux,
                    "reflux_flow": reflux,
                    "boilup_flow": boilup,
                    "sensor_bias": sensor_bias,
                    "sensor_drift": sensor_drift,
                    "sensor_noise": sensor_noise,
                    "sensor_residual": sensor_residual,
                    "sensor_residual_ewma": ewma,
                    "sensor_alarm": alarm,
                }
            )
            state = self.column.step(state, inputs, scenario.dt)

        return pd.DataFrame.from_records(records)
