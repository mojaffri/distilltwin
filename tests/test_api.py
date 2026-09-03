from fastapi.testclient import TestClient

from distilltwin.api import app

client = TestClient(app)


def test_health_and_metadata_are_honest_about_model_status() -> None:
    assert client.get("/health").json()["status"] == "ok"
    metadata = client.get("/metadata")
    assert metadata.status_code == 200
    assert "not yet calibrated against Aspen" in metadata.json()["status"]
    assert "scenario-level ridge soft-sensor validation" in metadata.json()[
        "implemented_capabilities"
    ]


def test_simulation_endpoint_returns_summary_and_timeseries() -> None:
    response = client.post(
        "/simulate",
        json={
            "duration": 12.0,
            "dt": 0.2,
            "disturbance_at": 5.0,
            "top_sensor_noise_std": 0.004,
            "top_sensor_drift_rate_after": 0.002,
            "random_seed": 17,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["samples"] == 61
    assert payload["summary"]["peak_absolute_sensor_ewma"] > 0.0
    assert len(payload["records"]) == 61
    assert "sensor_noise" in payload["records"][0]


def test_simulation_rejects_invalid_timing_and_unknown_fields() -> None:
    bad_timing = client.post(
        "/simulate", json={"duration": 10.0, "disturbance_at": 11.0}
    )
    unknown = client.post("/simulate", json={"mystery_parameter": 123})
    assert bad_timing.status_code == 422
    assert unknown.status_code == 422
