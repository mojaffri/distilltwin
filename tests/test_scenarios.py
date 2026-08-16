from distilltwin.scenarios import Scenario, ScenarioRunner


def test_feed_step_produces_a_bounded_closed_loop_response() -> None:
    frame = ScenarioRunner().run(
        Scenario(duration=30.0, dt=0.2, disturbance_at=10.0, feed_composition_after=0.62)
    )
    assert len(frame) == 151
    assert frame["x_top"].between(0.0, 1.0).all()
    assert frame["x_bottom"].between(0.0, 1.0).all()
    assert frame.loc[frame["time"] >= 10.0, "feed_composition"].eq(0.62).all()
    assert abs(frame["x_top"].iloc[-1] - frame["top_setpoint"].iloc[-1]) < 0.03


def test_sensor_bias_triggers_residual_alarm() -> None:
    frame = ScenarioRunner().run(
        Scenario(duration=25.0, dt=0.2, disturbance_at=10.0, top_sensor_bias_after=0.05)
    )
    assert frame.loc[frame["time"] < 10.0, "sensor_alarm"].sum() == 0
    assert frame.loc[frame["time"] >= 10.0, "sensor_alarm"].any()


def test_reflux_effectiveness_fault_changes_actual_not_commanded_flow() -> None:
    frame = ScenarioRunner().run(
        Scenario(
            duration=15.0,
            dt=0.2,
            disturbance_at=5.0,
            reflux_effectiveness_after=0.7,
        )
    )
    faulted = frame.loc[frame["time"] >= 5.0]
    ratio = faulted["reflux_flow"] / faulted["reflux_command"]
    assert (ratio - 0.7).abs().max() < 1e-12

