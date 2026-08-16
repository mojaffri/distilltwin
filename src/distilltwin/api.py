"""FastAPI boundary for health, metadata, and simulation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from distilltwin import __version__
from distilltwin.scenarios import Scenario, ScenarioRunner

app = FastAPI(
    title="DistillTwin API",
    version=__version__,
    description="Reproducible closed-loop experiments for a binary distillation column.",
)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration: float = Field(default=60.0, gt=0, le=240)
    dt: float = Field(default=0.1, ge=0.02, le=1.0)
    disturbance_at: float = Field(default=20.0, ge=0)
    feed_composition_after: float = Field(default=0.58, ge=0, le=1)
    feed_rate_after: float = Field(default=1.0, gt=0, le=3)
    top_sensor_bias_after: float = Field(default=0.0, ge=-0.2, le=0.2)
    reflux_effectiveness_after: float = Field(default=1.0, ge=0.5, le=1)

    @model_validator(mode="after")
    def validate_timing(self) -> ScenarioRequest:
        if self.disturbance_at > self.duration:
            raise ValueError("disturbance_at must not exceed duration")
        return self


class SimulationResponse(BaseModel):
    summary: dict[str, float | int]
    records: list[dict[str, Any]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    return {
        "model": "binary equilibrium-stage column under constant molar overflow",
        "status": "open control-oriented model; not yet calibrated against Aspen",
        "default_stage_count": 8,
        "implemented_capabilities": [
            "dynamic component balances",
            "paired PID control with anti-windup",
            "feed disturbances",
            "sensor bias and actuator effectiveness faults",
            "online EWMA residual alarms",
        ],
    }


@app.post("/simulate", response_model=SimulationResponse)
def simulate(request: ScenarioRequest) -> SimulationResponse:
    frame = ScenarioRunner().run(Scenario(**request.model_dump()))
    summary: dict[str, float | int] = {
        "samples": len(frame),
        "final_top_composition": float(frame["x_top"].iloc[-1]),
        "final_bottom_composition": float(frame["x_bottom"].iloc[-1]),
        "peak_top_control_error": float(
            (frame["x_top"] - frame["top_setpoint"]).abs().max()
        ),
        "alarm_samples": int(frame["sensor_alarm"].sum()),
    }
    return SimulationResponse(summary=summary, records=frame.to_dict(orient="records"))
