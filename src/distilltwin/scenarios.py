"""Closed-loop disturbance and fault scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np
import pandas as pd

from distilltwin.analytics import EWMAResidualMonitor
from distilltwin.control import PIDConfig, PIDController
from distilltwin.estimation import ExtendedKalmanFilter, MeasurementConfig, MeasurementModel
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
    reflux_effectiveness_after: float = 1.0

    def __post_init__(self) -> None:
        values = (
            self.duration,
            self.dt,
            self.disturbance_at,
            self.feed_composition_after,
            self.feed_rate_after,
            self.top_sensor_bias_after,
            self.reflux_effectiveness_after,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("scenario values must be finite")
        if self.duration <= 0 or self.dt <= 0:
            raise ValueError("duration and dt must be positive")
        if not 0.0 <= self.disturbance_at <= self.duration:
            raise ValueError("disturbance_at must fall within the simulation")
        if not 0.0 <= self.feed_composition_after <= 1.0:
            raise ValueError("feed composition must be between zero and one")
        if self.feed_rate_after <= 0:
            raise ValueError("feed rate must be positive")
        if not 0.5 <= self.reflux_effectiveness_after <= 1.0:
            raise ValueError("reflux effectiveness must be between 0.5 and 1.0")


def _boilup_limits(
    reflux: float,
    feed_rate: float,
    configured_minimum: float,
    configured_maximum: float,
) -> tuple[float, float]:
    """Combine operating limits with stricter product-flow feasibility limits."""
    margin = min(0.05, feed_rate / 4.0)
    physical_minimum = reflux + margin
    physical_maximum = reflux + feed_rate - margin
    lower = max(configured_minimum, physical_minimum)
    upper = min(configured_maximum, physical_maximum)
    if lower >= upper:
        return physical_minimum, physical_maximum
    return lower, upper


class ScenarioRunner:
    """Run paired composition controllers around the dynamic column model."""

    def __init__(self, column: DistillationColumn | None = None) -> None:
        self.column = column or DistillationColumn()

    def run(self, scenario: Scenario) -> pd.DataFrame:
        cfg = self.column.config
        state = self.column.steady_state()
        top_setpoint = float(state[-1])
        bottom_setpoint = float(state[0])

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
        observer_column = DistillationColumn(cfg)
        observer_measurements = MeasurementModel(
            observer_column,
            MeasurementConfig(
                composition_stages=(0,),
                temperature_stages=(cfg.n_stages // 3, 2 * cfg.n_stages // 3),
            ),
        )
        observer = ExtendedKalmanFilter(
            observer_column,
            observer_measurements,
            initial_state=observer_column.steady_state(),
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
            effectiveness = scenario.reflux_effectiveness_after if disturbed else 1.0
            measured_top = float(np.clip(state[-1] + sensor_bias, 0.0, 1.0))
            measured_bottom = float(state[0])

            commanded_reflux = top_controller.update(
                setpoint=top_setpoint,
                measurement=measured_top,
                dt=scenario.dt,
            )
            reflux = commanded_reflux * effectiveness
            boilup_minimum, boilup_maximum = _boilup_limits(
                reflux,
                feed_rate,
                bottom_controller.config.output_min,
                bottom_controller.config.output_max,
            )
            commanded_boilup = bottom_controller.update(
                setpoint=bottom_setpoint,
                measurement=measured_bottom,
                dt=scenario.dt,
                output_min=boilup_minimum,
                output_max=boilup_maximum,
            )
            boilup = commanded_boilup

            inputs = ColumnInputs(feed_rate, feed_composition, reflux, boilup)
            temperatures = self.column.temperature_proxy(state)
            observer_measurement = observer_measurements.observe(state)
            estimated_state = observer.correct(observer_measurement).state
            top_residual = measured_top - float(estimated_state[-1])
            ewma, alarm = monitor.update(top_residual)
            records.append(
                {
                    "time": float(time),
                    "x_bottom": float(state[0]),
                    "x_top": float(state[-1]),
                    "measured_top": measured_top,
                    "top_setpoint": top_setpoint,
                    "bottom_setpoint": bottom_setpoint,
                    "temperature_bottom": float(temperatures[0]),
                    "temperature_top": float(temperatures[-1]),
                    "estimated_x_bottom": float(estimated_state[0]),
                    "estimated_x_top": float(estimated_state[-1]),
                    "feed_rate": feed_rate,
                    "feed_composition": feed_composition,
                    "reflux_command": commanded_reflux,
                    "reflux_flow": reflux,
                    "boilup_flow": boilup,
                    "sensor_residual_ewma": ewma,
                    "sensor_alarm": alarm,
                }
            )
            state = self.column.step(state, inputs, scenario.dt)
            observer.predict(inputs, scenario.dt)

        return pd.DataFrame.from_records(records)
