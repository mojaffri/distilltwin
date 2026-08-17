# Changelog

All notable changes to DistillTwin are documented here.

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
