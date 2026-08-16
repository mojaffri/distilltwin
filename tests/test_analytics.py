import numpy as np
import pytest

from distilltwin.analytics import EWMAResidualMonitor, RidgeSoftSensor


def test_soft_sensor_learns_linear_relationship() -> None:
    rng = np.random.default_rng(7)
    features = rng.normal(size=(200, 3))
    target = 0.5 + features @ np.array([0.05, -0.03, 0.02])
    sensor = RidgeSoftSensor(regularization=1e-6).fit(features[:150], target[:150])
    assert sensor.rmse(features[150:], target[150:]) < 1e-4


def test_soft_sensor_requires_fit() -> None:
    with pytest.raises(RuntimeError, match="fit"):
        RidgeSoftSensor().predict(np.ones((2, 2)))


def test_ewma_monitor_alarms_on_persistent_bias() -> None:
    monitor = EWMAResidualMonitor(smoothing=0.3, alarm_threshold=0.02)
    alarms = [monitor.update(0.05)[1] for _ in range(5)]
    assert any(alarms)

