# Changelog

All notable changes to DistillTwin are documented here.

## Unreleased

### State estimation

- Added a configurable partial-measurement model and discrete extended Kalman filter
- Added the analytical stage-balance Jacobian and its RK4 state-transition propagation
- Added hidden-plant benchmarks for nominal operation, unmeasured feed disturbances,
  sensor noise, relative-volatility mismatch, and holdup mismatch
- Added overall, transient, peak, convergence, and per-stage RMSE outputs
- Replaced the analyzer residual's use of hidden simulator truth with a reference EKF
- Removed the unbenchmarked ridge soft-sensor utility and its synthetic-only test

### Correctness and verification

- Reject non-finite model, controller, scenario, and API values
- Reject integration steps that leave the physical composition domain
- Apply product-flow feasibility as active PID limits so the integral term does not
  wind up against a downstream projection
- Added estimator, analytical-linearization, invalid-state, dynamic-limit, API, and
  interface regression tests

## 1.0.0 — 2026-08-17

First release of the open, control-oriented digital twin.

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
- Streamlit validation lab

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
