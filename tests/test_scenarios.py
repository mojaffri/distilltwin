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


def test_low_feed_rate_keeps_product_flows_physically_valid() -> None:
    frame = ScenarioRunner().run(
        Scenario(
            duration=8.0,
            dt=0.2,
            disturbance_at=2.0,
            feed_rate_after=0.02,
        )
    )
    disturbed = frame.loc[frame["time"] >= 2.0]
    distillate = disturbed["boilup_flow"] - disturbed["reflux_flow"]
    bottoms = disturbed["reflux_flow"] + disturbed["feed_rate"] - disturbed["boilup_flow"]
    assert (distillate > 0.0).all()
    assert (bottoms > 0.0).all()


def test_seeded_analyzer_noise_is_reproducible() -> None:
    runner = ScenarioRunner()
    case = Scenario(
        duration=4.0,
        dt=0.2,
        disturbance_at=2.0,
        top_sensor_noise_std=0.004,
        random_seed=19,
    )
    first = runner.run(case)
    repeated = runner.run(case)
    different = runner.run(Scenario(**{**case.__dict__, "random_seed": 20}))
    assert first["sensor_noise"].equals(repeated["sensor_noise"])
    assert not first["sensor_noise"].equals(different["sensor_noise"])


def test_gradual_analyzer_drift_accumulates_after_fault_time() -> None:
    frame = ScenarioRunner().run(
        Scenario(
            duration=8.0,
            dt=0.2,
            disturbance_at=3.0,
            feed_composition_after=0.50,
            top_sensor_drift_rate_after=0.003,
        )
    )
    before = frame.loc[frame["time"] < 3.0]
    after = frame.loc[frame["time"] >= 3.0]
    assert before["sensor_drift"].eq(0.0).all()
    assert after["sensor_drift"].is_monotonic_increasing
    assert after["sensor_drift"].iloc[-1] == 0.015
