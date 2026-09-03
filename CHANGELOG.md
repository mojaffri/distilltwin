# Changelog

All notable changes to DistillTwin are documented here.

## 1.1.0 — 2026-09-03

### Analytics validation

- Added complete-scenario train/holdout evaluation for the ridge soft sensor
- Excluded the directly invertible top-temperature proxy and injected deterministic
  `0.15 degC` noise into selected tray-temperature features
- Measured `0.000347` holdout RMSE, a 94.5% reduction from the constant baseline

### Fault robustness

- Added reproducible analyzer noise and gradual drift to the scenario model
- Added positive-bias, negative-bias, gradual-drift, and no-fault benchmarks across
  12 seeded noise realizations
- Reported detection rate, median and P95 delay, pre-fault alarms, and alarm persistence
- Exported the full fault-suite summary with every validation bundle

### Interfaces

- Exposed noise, drift, and random-seed controls through the API, CLI, and Streamlit lab
- Added selected tray temperatures, raw residuals, and injected sensor-error components
  to scenario time series
- Added a Streamlit render smoke test for the control-room and validation views

## 1.0.0 — 2026-08-17

First portfolio-ready release of the open, control-oriented digital twin.

### Engineering model

- Eight-stage binary equilibrium column with total condenser and partial reboiler
- Nonlinear constant-relative-volatility VLE and component material balances
- RK4 dynamic integration and numerical steady-state initialization
- Paired top/bottom PID composition control with saturation and anti-windup
- Feed disturbances, analyzer bias, and reflux-valve effectiveness faults
- EWMA residual monitoring and a ridge-regression soft sensor

### Validation evidence

- Automated light-key balance closure and steady-state residual checks
- Fixed-input open-loop versus paired-PID disturbance-response benchmarks
- IAE, ISE, peak error, final error, and settling-time metrics
- RK4 timestep-sensitivity study against a finer reference
- Known analyzer-bias detection delay and false-alarm measurements
- Reproducible Markdown, JSON, and CSV validation bundle
- Recruiter-visible Streamlit Validation Lab

### Software delivery

- FastAPI service, interactive Streamlit application, and CSV-export CLI
- Docker and Docker Compose packaging
- Python 3.11/3.12 CI with Ruff, strict Mypy, pytest, and 90% coverage gate
- Containerized API runtime smoke test
- Dependabot maintenance and documented Aspen Plus/Dynamics handoff

### Validation boundary

Version 1.0.0 verifies the transparent reduced-order model within its documented
assumptions. Agreement with Aspen Plus, Aspen Plus Dynamics, or plant data is not
claimed and remains future licensed work.
