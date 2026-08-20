from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_and_renders_validation_results() -> None:
    app_path = Path(__file__).parents[1] / "webapp" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=120)

    assert not app.exception
    assert app.title[0].value == "DistillTwin Engineering Lab"
    assert any(
        "EKF state-estimation benchmark" in subheader.value
        for subheader in app.subheader
    )
