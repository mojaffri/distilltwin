from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_and_exposes_validation_run() -> None:
    app_path = Path(__file__).parents[1] / "webapp" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=120)

    assert not app.exception
    assert app.title[0].value == "DistillTwin Engineering Lab"
    assert app.button[0].label == "Run validation benchmarks"
