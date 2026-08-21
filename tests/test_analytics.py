import pytest

from distilltwin.analytics import EWMAResidualMonitor


def test_ewma_monitor_alarms_on_persistent_bias() -> None:
    monitor = EWMAResidualMonitor(smoothing=0.3, alarm_threshold=0.02)
    alarms = [monitor.update(0.05)[1] for _ in range(5)]
    assert any(alarms)


def test_monitor_rejects_nonfinite_data_and_invalid_tuning() -> None:
    with pytest.raises(ValueError, match="alarm_threshold"):
        EWMAResidualMonitor(alarm_threshold=0.0)
    with pytest.raises(ValueError, match="residual"):
        EWMAResidualMonitor().update(float("nan"))

