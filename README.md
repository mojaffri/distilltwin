# DistillTwin

[![CI](https://github.com/mojaffri/distilltwin/actions/workflows/ci.yml/badge.svg)](https://github.com/mojaffri/distilltwin/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An open, dynamic digital twin of a binary distillation column for process-control,
fault-detection, and time-series experiments—with a documented path to rigorous
Aspen Plus and Aspen Plus Dynamics validation.

DistillTwin is intentionally a different engineering story from
[Titrate](https://github.com/mojaffri/titrate). Titrate demonstrates scientific ML
and MLOps; this repository demonstrates dynamic process modeling, feedback control,
fault injection, industrial analytics, API design, containerization, and eventually
commercial-simulator integration.

> **Current validation boundary:** the open Python model is implemented and tested.
> It has **not** yet been calibrated against Aspen. Aspen work is labeled as planned
> until it is performed through licensed university access.

## What is working now

- Dynamic light-key component balances across eight equilibrium stages
- Total condenser, partial reboiler, saturated-liquid feed, and nonlinear VLE
- Fourth-order Runge-Kutta integration and a numerical steady-state initializer
- Paired top/bottom composition PID loops with saturation and anti-windup
- Feed-composition and feed-rate disturbances
- Analyzer-bias and reflux-valve-effectiveness fault injection
- EWMA residual alarms and a dependency-light ridge-regression soft sensor
- Interactive Streamlit control room
- FastAPI service with validated scenario inputs and OpenAPI documentation
- CLI scenario export, Docker/Compose packaging, tests, linting, typing, and CI

## Architecture

~~~mermaid
flowchart LR
    UI[Streamlit control room] --> SC[Scenario runner]
    API[FastAPI service] --> SC
    CLI[CLI experiment] --> SC
    SC --> PID[Paired PID controllers]
    PID --> COL[Dynamic staged-column model]
    COL --> TS[Process time series]
    TS --> FD[EWMA fault monitor]
    TS --> SS[Ridge soft sensor]
    ASPEN[Aspen Plus / Dynamics adapter<br/>planned, license required] -. calibration and validation .-> COL
~~~

The open model uses constant relative volatility and constant molar overflow. That
makes every balance auditable and simulations fast enough for controls and analytics.
The future Aspen layer will add rigorous thermodynamics, equipment sizing, pressure
dynamics, and a higher-fidelity validation reference.

## Run it locally

~~~bash
git clone https://github.com/mojaffri/distilltwin.git
cd distilltwin
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
~~~

Launch the interactive process-control lab:

~~~bash
streamlit run webapp/app.py
~~~

Launch the API and open http://localhost:8000/docs:

~~~bash
uvicorn distilltwin.api:app --reload
~~~

Run a repeatable experiment and export its time series:

~~~bash
distilltwin --feed-composition 0.62 --sensor-bias 0.03
~~~

Or run both services with containers:

~~~bash
docker compose up --build
# API:       http://localhost:8000/docs
# Dashboard: http://localhost:8501
~~~

## API example

~~~bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "duration": 60,
    "disturbance_at": 20,
    "feed_composition_after": 0.62,
    "top_sensor_bias_after": 0.03
  }'
~~~

The response includes final product compositions, peak control error, alarm count,
and the complete process time series.

## Verification

~~~bash
ruff check .
mypy src
pytest
docker build -t distilltwin .
~~~

The test suite checks VLE behavior, overall light-key conservation, steady-state
convergence, numerical bounds, controller direction and anti-windup, fault injection,
soft-sensor behavior, alarm activation, API contracts, and invalid-input handling.

## Model assumptions and limitations

| Area | Implemented assumption | Aspen validation target |
|---|---|---|
| Thermodynamics | Constant relative volatility | Property-method comparison and rigorous VLE |
| Hydraulics | Constant molar overflow and fixed stage holdups | Tray sizing, pressure drop, and equipment holdup |
| Feed | Saturated liquid | Flash-derived feed condition |
| Heat balance | Temperature proxy from composition | Full enthalpy balances |
| Control | Composition control with ideal analyzers plus injected faults | Temperature inferential control, valve dynamics, dead time |
| Fidelity | Control-oriented educational model | Aspen Plus steady state and Aspen Plus Dynamics transients |

These assumptions are features of the experiment design, not hidden claims. The
reduced-order model remains useful after Aspen integration: it becomes the fast
surrogate/control sandbox, while Aspen provides a rigorous reference.

## Aspen integration plan

The licensed work is designed as a short, high-value campus session:

1. Build and converge a rigorous binary column in Aspen Plus.
2. Export a steady-state operating point and sanitized reference data.
3. Convert the case to Aspen Plus Dynamics and configure pressure-driven equipment.
4. Run the same feed steps and faults defined in this repository.
5. Compare steady states, transient trajectories, settling time, and integral error.
6. Add a Windows COM adapter so Python can run repeatable Aspen experiments.

The exact checklist, data contract, and “do not overclaim” rules are in
[docs/ASPEN_HANDOFF.md](docs/ASPEN_HANDOFF.md). No paid cloud service is required.
GitHub Actions is sufficient for the open model's CI; Aspen itself stays on the
licensed school machine/network.

## Repository map

~~~text
src/distilltwin/
├── model.py        # stage balances, VLE, RK4, steady state
├── control.py      # PID with limits and anti-windup
├── scenarios.py    # closed-loop disturbances and faults
├── analytics.py    # soft sensor and residual monitoring
├── api.py          # validated FastAPI service
└── cli.py          # reproducible CSV experiment runner
webapp/app.py       # recruiter-visible interactive control room
tests/              # physics, controls, analytics, and API tests
docs/               # architecture decisions and Aspen handoff
~~~

## Skills demonstrated

Chemical/process engineering, dynamic simulation, material balances, VLE,
process control, PID tuning, numerical methods, disturbance testing, fault
detection, time-series analysis, soft sensors, Python package design, FastAPI,
Streamlit, Docker, GitHub Actions, automated testing, static typing, and technical
documentation.

## License

MIT
