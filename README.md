# DistillTwin

[![CI](https://github.com/mojaffri/distilltwin/actions/workflows/ci.yml/badge.svg)](https://github.com/mojaffri/distilltwin/actions/workflows/ci.yml)
[![Coverage ≥90%](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen.svg)](pyproject.toml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Version 1.0.0](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An open, dynamic digital twin of a binary distillation column for process control,
fault detection, and reproducible engineering experiments—with a documented path to
rigorous Aspen Plus and Aspen Plus Dynamics validation.

DistillTwin is intentionally a different engineering story from
[Titrate](https://github.com/mojaffri/titrate). Titrate demonstrates scientific ML
and MLOps; this repository demonstrates dynamic process modeling, feedback control,
fault injection, industrial analytics, numerical verification, API design,
containerization, and eventually commercial-simulator integration.

> **Current validation boundary:** the Python model is implemented, tested, and
> validated within its documented reduced-order assumptions. It has **not** been
> calibrated against Aspen or plant data. Commercial-simulator work remains explicitly
> labeled as planned until performed through licensed university access.

## Engineering evidence

- Dynamic light-key balances across eight equilibrium stages
- Total condenser, partial reboiler, saturated-liquid feed, and nonlinear VLE
- Fourth-order Runge-Kutta integration and a numerical steady-state initializer
- Paired top/bottom composition PID loops with saturation and anti-windup
- Feed-composition and feed-rate disturbances
- Analyzer-bias and reflux-valve-effectiveness fault injection
- EWMA residual alarms and a dependency-light ridge-regression soft sensor
- Open-loop versus paired-PID IAE, ISE, peak-error, final-error, and settling benchmarks
- Automated material-balance, steady-state, and RK4 timestep-sensitivity checks
- Known-fault detection delay, false-alarm, and post-fault alarm measurements
- Interactive Streamlit control room and recruiter-facing Validation Lab
- FastAPI service with validated inputs and generated OpenAPI documentation
- CLI experiment and validation exports, Docker/Compose, typing, linting, tests, and CI
- Enforced 90% test-coverage floor across Python 3.11 and 3.12
- Containerized API runtime smoke test—not only a Docker build check

## Architecture

~~~mermaid
flowchart LR
    UI[Streamlit Engineering Lab] --> SC[Scenario runner]
    API[FastAPI service] --> SC
    CLI[CLI experiments] --> SC
    SC --> PID[Paired PID controllers]
    PID --> COL[Dynamic staged-column model]
    COL --> TS[Process time series]
    TS --> FD[EWMA fault monitor]
    TS --> SS[Ridge soft sensor]
    COL --> VAL[Validation suite]
    SC --> VAL
    VAL --> EV[Markdown, JSON, and CSV evidence]
    ASPEN[Aspen Plus / Dynamics adapter<br/>planned, license required] -. calibration and validation .-> COL
~~~

The open model uses constant relative volatility and constant molar overflow. This
keeps every balance auditable and makes simulations fast enough for control and
analytics experiments. The future Aspen layer will add rigorous thermodynamics,
equipment sizing, pressure dynamics, and a higher-fidelity reference.

## Interactive Engineering Lab

~~~bash
git clone https://github.com/mojaffri/distilltwin.git
cd distilltwin
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
streamlit run webapp/app.py
~~~

The **Control room** tab provides adjustable feed, sensor, and valve scenarios with
live composition, manipulated-variable, temperature, and alarm plots.

The **Validation lab** presents balance closure, steady-state stationarity, paired-PID
improvement, timestep sensitivity, and fault-detection metrics. Its report can be
downloaded directly from the interface.

## Generate reproducible validation evidence

~~~bash
distilltwin-validate --output validation-report
~~~

The command creates:

- a reviewer-readable Markdown report;
- structured JSON results;
- an open-loop/PID benchmark CSV; and
- an RK4 timestep-sensitivity CSV.

GitHub Actions generates and uploads the same bundle on every pull request. See the
[validated reference results](docs/VALIDATION_RESULTS.md) for the current metrics and
[validation strategy](docs/VALIDATION.md) for the experimental design, acceptance
thresholds, and evidence boundaries.

## API and CLI

Launch the API and open http://localhost:8000/docs:

~~~bash
uvicorn distilltwin.api:app --reload
~~~

Example scenario:

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

## Verification

~~~bash
ruff check .
mypy src
pytest
distilltwin-validate --output validation-report
docker build -t distilltwin .
~~~

CI executes the quality suite on Python 3.11 and 3.12, refuses coverage below 90%,
builds the production image, launches it as a non-root user, and calls the real
containerized `/health` endpoint.

The tests cover VLE behavior, overall light-key conservation, steady-state
convergence, physical bounds, controller direction and anti-windup, open-loop/PID
performance, timestep sensitivity, fault injection and detection, soft-sensor
behavior, API contracts, command-line exports, validation artifacts, and invalid
inputs.

## Model assumptions and limitations

| Area | Implemented assumption | Aspen validation target |
|---|---|---|
| Thermodynamics | Constant relative volatility | Property-method comparison and rigorous VLE |
| Hydraulics | Constant molar overflow and fixed stage holdups | Tray sizing, pressure drop, and equipment holdup |
| Feed | Saturated liquid | Flash-derived feed condition |
| Heat balance | Temperature proxy from composition | Full enthalpy balances |
| Control | Composition control with ideal analyzers plus injected faults | Temperature inference, valve dynamics, and dead time |
| Fidelity | Control-oriented reduced-order model | Aspen Plus steady state and Aspen Plus Dynamics transients |

These assumptions are visible experimental choices, not hidden fidelity claims. The
reduced-order model remains valuable after Aspen integration as a fast control
sandbox, while Aspen becomes the rigorous reference.

## Aspen integration plan

The licensed work is designed as a short, high-value campus session:

1. Build and converge a rigorous binary column in Aspen Plus.
2. Export a steady-state operating point and sanitized reference data.
3. Convert the case to Aspen Plus Dynamics and configure pressure-driven equipment.
4. Run the same feed steps and faults defined in this repository.
5. Compare steady states, trajectories, settling time, and integral error.
6. Add a Windows COM adapter for repeatable Python-orchestrated experiments.

The exact checklist, data contract, and “do not overclaim” rules are in
[docs/ASPEN_HANDOFF.md](docs/ASPEN_HANDOFF.md). No paid cloud service is required:
GitHub Actions validates the open model, while Aspen remains on the licensed school
machine and network.

## Repository map

~~~text
src/distilltwin/
├── model.py        # stage balances, VLE, RK4, steady state
├── control.py      # PID with limits and anti-windup
├── scenarios.py    # closed-loop disturbances and faults
├── analytics.py    # soft sensor and residual monitoring
├── validation.py   # physics, control, numerical, and fault benchmarks
├── api.py          # validated FastAPI service
└── cli.py          # reproducible CSV experiment runner
webapp/app.py       # interactive Control Room and Validation Lab
tests/              # physics, controls, analytics, interfaces, and validation
docs/               # architecture, validation strategy, and Aspen handoff
CHANGELOG.md        # portfolio-ready release history
~~~

## Skills demonstrated

Chemical/process engineering, dynamic simulation, component material balances, VLE,
process control, PID tuning, numerical methods, convergence studies, disturbance
testing, fault injection, anomaly detection, control-performance metrics, time-series
analysis, soft sensors, experimental design, Python package design, FastAPI,
Streamlit, Docker, GitHub Actions, CI/CD, automated testing, code coverage, static
typing, dependency maintenance, and technical documentation.

## Release and license

See [CHANGELOG.md](CHANGELOG.md) for the 1.0.0 portfolio release. Licensed under MIT.
