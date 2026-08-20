import pytest

from distilltwin.control import PIDConfig, PIDController


def test_pid_respects_limits_and_prevents_integral_runaway() -> None:
    controller = PIDController(
        PIDConfig(kp=10.0, ki=5.0, output_min=0.0, output_max=1.0)
    )
    outputs = [
        controller.update(setpoint=1.0, measurement=0.0, dt=0.1) for _ in range(100)
    ]
    assert outputs == [1.0] * 100
    assert controller.integral == pytest.approx(0.0)


def test_reverse_action_changes_output_in_expected_direction() -> None:
    controller = PIDController(
        PIDConfig(kp=2.0, ki=0.0, bias=3.0, output_min=2.0, output_max=4.0, action=-1)
    )
    assert controller.update(setpoint=0.1, measurement=0.2, dt=0.1) > 3.0


def test_pid_rejects_nonpositive_timestep() -> None:
    controller = PIDController(PIDConfig(kp=1.0, ki=0.0))
    with pytest.raises(ValueError, match="positive"):
        controller.update(setpoint=1.0, measurement=0.0, dt=0.0)


def test_pid_tracks_dynamic_output_limits_without_windup() -> None:
    controller = PIDController(
        PIDConfig(kp=3.0, ki=1.0, bias=3.0, output_min=2.0, output_max=4.0)
    )
    outputs = [
        controller.update(
            setpoint=1.0,
            measurement=0.0,
            dt=0.1,
            output_min=2.50,
            output_max=2.55,
        )
        for _ in range(20)
    ]
    assert outputs == [2.55] * 20
    assert controller.integral == pytest.approx(0.0)


def test_pid_rejects_nonfinite_values_and_invalid_active_limits() -> None:
    controller = PIDController(PIDConfig(kp=1.0, ki=0.0))
    with pytest.raises(ValueError, match="finite"):
        controller.update(setpoint=1.0, measurement=float("nan"), dt=0.1)
    with pytest.raises(ValueError, match="ordered"):
        controller.update(
            setpoint=1.0,
            measurement=0.0,
            dt=0.1,
            output_min=1.0,
            output_max=1.0,
        )

