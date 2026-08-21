from fastapi.testclient import TestClient

from distilltwin.api import app

client = TestClient(app)


def test_health_and_metadata_report_model_status() -> None:
    assert client.get("/health").json()["status"] == "ok"
    metadata = client.get("/metadata")
    assert metadata.status_code == 200
    assert "not yet calibrated against Aspen" in metadata.json()["status"]


def test_simulation_endpoint_returns_summary_and_timeseries() -> None:
    response = client.post(
        "/simulate",
        json={"duration": 12.0, "dt": 0.2, "disturbance_at": 5.0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["samples"] == 61
    assert len(payload["records"]) == 61


def test_simulation_rejects_invalid_timing_and_unknown_fields() -> None:
    bad_timing = client.post(
        "/simulate", json={"duration": 10.0, "disturbance_at": 11.0}
    )
    unknown = client.post("/simulate", json={"mystery_parameter": 123})
    nonfinite = client.post(
        "/simulate",
        content='{"duration": NaN}',
        headers={"content-type": "application/json"},
    )
    assert bad_timing.status_code == 422
    assert unknown.status_code == 422
    assert nonfinite.status_code == 422
