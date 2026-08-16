# Architecture decisions

## Why distillation

Distillation adds staged separation, vapor-liquid equilibrium, multivariable control,
and industrial fault scenarios without repeating Titrate's CSTR optimization story.

## Why an open model first

The open model makes development, tests, CI, the API, and the dashboard runnable on
any machine. Aspen later supplies rigorous thermodynamics and dynamics; it does not
become a hidden runtime dependency for the public project.

## Why both physics and analytics

Physics generates interpretable trajectories and enforces conservation. Analytics
adds soft sensing and residual alarms. Keeping both layers visible demonstrates where
first-principles knowledge ends and data-driven inference begins.

## Trust boundaries

- API inputs are schema-validated and reject unknown fields.
- Model inputs reject infeasible product-flow combinations.
- Controller outputs are saturated and projected into the feasible flow region.
- No credentials, license-server settings, or Aspen binaries belong in Git.
- Public status text distinguishes implemented, tested, and planned work.

