# Architecture decisions

## Why distillation

Distillation adds staged separation, vapor-liquid equilibrium, multivariable control,
and industrial fault scenarios without repeating Titrate's CSTR optimization story.

## Why an open model first

The open model makes development, tests, CI, the API, and the dashboard runnable on
any machine. Aspen later supplies rigorous thermodynamics and dynamics; it does not
become a hidden runtime dependency for the public project.

## Why both physics and analytics

Physics generates interpretable trajectories and enforces conservation. The estimator
uses that model with partial measurements, while residual monitoring evaluates a
defined analyzer fault against an independent reference-observer signal.

## Plant and twin separation

Estimator benchmarks construct a hidden plant separately from the model used by the
EKF. Measurements cross that boundary; plant state vectors do not. Defined changes to
relative volatility and stage holdups quantify the effect of structural mismatch
without implying calibration to a commercial simulator or operating unit.

## Trust boundaries

- API inputs are schema-validated and reject unknown fields.
- Model inputs and states reject non-finite and physically invalid values.
- Controller outputs use dynamic limits that keep both product rates positive and
  prevent integration against the applied feasibility limit.
- Fault residuals compare measurements with a reference observer rather than hidden
  simulator truth.
- No credentials, license-server settings, or Aspen binaries belong in Git.
- Public status text distinguishes implemented, tested, and planned work.

