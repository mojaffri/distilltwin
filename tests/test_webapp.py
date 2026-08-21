from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_and_exposes_primary_workflows() -> None:
    app_path = Path(__file__).parents[1] / "webapp" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=120)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Live scenario", "Validation evidence"]
    assert app.button[0].label == "Run validation benchmarks"
    assert len(app.metric) == 4
    assert app.metric[0].label == "Final top purity"
