from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_engineering_lab_renders_without_exceptions() -> None:
    app_path = Path(__file__).parents[1] / "webapp" / "app.py"
    app = AppTest.from_file(app_path).run(timeout=60)
    assert not app.exception
    assert [title.value for title in app.title] == ["DistillTwin Engineering Lab"]
    assert [tab.label for tab in app.tabs] == ["Control room", "Validation lab"]
    metric_labels = {metric.label for metric in app.metric}
    assert "Soft-sensor holdout RMSE" in metric_labels
    assert "Minimum noisy detection rate" in metric_labels
