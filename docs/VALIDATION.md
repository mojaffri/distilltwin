# Validation strategy

DistillTwin keeps three evidence levels separate: software and numerical verification,
validation of the reduced-order model against its own stated assumptions, and future
comparison with higher-fidelity simulators or plant data.

## Evidence levels

| Level | Question | Current evidence |
|---|---|---|
| Code verification | Is the software behaving as specified? | Unit, integration, API, CLI, typing, linting, and container checks |
| Physics verification | Do the implemented equations conserve the light key and reach a stationary solution? | Balance-closure and steady-state residual metrics |
| Numerical verification | How sensitive is the reported trajectory to RK4 timestep? | Automated timestep-sensitivity study |
| Control validation | Do the PID loops improve disturbance rejection versus fixed manipulated variables? | Open-loop/PID IAE, ISE, peak error, final error, and settling-time comparison |
| Fault-monitor validation | Does the EWMA monitor detect the defined analyzer-bias injection? | Detection delay, pre-fault alarm fraction, and post-fault alarm fraction |
| Commercial-simulator validation | How closely does the reduced-order model match a rigorous simulator? | Planned Aspen Plus/Dynamics comparison |
| Plant validation | How closely does the model match operating data? | No plant dataset is included |

## Reproduce the report

Install the development environment and run:

~~~bash
distilltwin-validate --output validation-report
~~~

The command writes `VALIDATION_REPORT.md`, `validation_report.json`,
`control_benchmark.csv`, and `timestep_sensitivity.csv`. CI runs the same validation
command on pull requests and uploads the Python 3.12 output as a workflow artifact.
The test suite enforces the acceptance criteria below.

## Experimental design

### Physics

Light-key accumulation is calculated by weighting each stage derivative by its holdup
and comparing the result with the external feed-minus-product component flux. The
steady-state check reports the maximum absolute derivative, composition range, and
stage-profile monotonicity.

### Control

A feed light-key step from 0.50 to 0.62 is simulated at fixed nominal reflux and boilup,
then repeated with the paired top/bottom PID loops active. Both cases begin from the
same numerically converged nominal state. Performance metrics are calculated after the
disturbance. Settling requires the absolute composition error to remain below 0.01.

### Numerical sensitivity

Closed-loop scenarios are repeated at several timesteps and compared with a
`dt = 0.05 min` reference. Final top and bottom product differences quantify the
observed discretization sensitivity for this model and scenario.

### Fault detection

A persistent +0.05 top-analyzer bias is injected at a known time. The report records
detection delay, the pre-fault alarm fraction, and the post-fault alarm fraction. This
benchmark covers the defined deterministic injection; noisy plant-data performance has
not been measured.

## Acceptance gates

The automated suite requires:

- absolute light-key balance residual below `1e-12`;
- nominal steady-state maximum derivative below `3e-8`;
- physically bounded, monotonic nominal composition;
- lower final top and bottom error with paired PID control;
- lower top-composition IAE with paired PID control;
- final top and bottom product differences below `5e-4` across every tested timestep
  and below `5e-5` at `dt = 0.1 min`;
- detection of the defined analyzer bias with zero pre-fault alarms in the deterministic
  benchmark.

These thresholds apply to the current reduced-order model and validation scenarios.
They should be re-evaluated when a higher-fidelity reference is added.
