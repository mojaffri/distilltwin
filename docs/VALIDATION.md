# Validation strategy

DistillTwin separates **verification**, **reduced-order validation**, and future
**high-fidelity validation** so that the evidence remains technically honest.

## Evidence levels

| Level | Question | Current evidence |
|---|---|---|
| Code verification | Is the software behaving as specified? | Unit, integration, API, CLI, typing, linting, and container checks |
| Physics verification | Do the implemented equations conserve the light key and reach a stationary solution? | Balance-closure and steady-state residual metrics |
| Numerical verification | Is the reported trajectory insensitive to a smaller RK4 timestep? | Automated timestep-sensitivity study |
| Control validation | Do the PID loops improve disturbance rejection versus fixed manipulated variables? | Open-loop/PID IAE, ISE, peak, final-error, and settling-time comparison |
| Fault-monitor validation | Does the EWMA monitor detect a known analyzer bias without pre-fault alarms? | Detection delay, false-alarm fraction, and post-fault alarm fraction |
| Soft-sensor validation | Does the ridge model generalize beyond the operating scenarios used for fitting? | Complete-scenario holdout with noisy selected tray-temperature features and a constant baseline |
| Fault-monitor robustness | Does detection survive measurement noise, bias direction, and gradual drift? | Repeated seeded-noise tests with detection-rate and delay distributions plus no-fault runs |
| Commercial-simulator validation | Does the reduced-order model agree with rigorous thermodynamics and equipment dynamics? | Planned Aspen Plus/Dynamics comparison; not yet claimed |
| Plant validation | Does the model match real operating data? | Out of scope until appropriate data is available |

## Reproduce the report

Install the development environment and run:

~~~bash
distilltwin-validate --output validation-report
~~~

This produces:

- `VALIDATION_REPORT.md` for a human-readable review;
- `validation_report.json` for programmatic inspection;
- `control_benchmark.csv` for the open-loop/PID comparison;
- `timestep_sensitivity.csv` for numerical convergence evidence; and
- `fault_suite.csv` for the repeated noisy fault benchmark.

CI runs the same command on every pull request and uploads the bundle from Python
3.12 as a workflow artifact. The test suite also enforces the physical and performance
acceptance criteria.

## Experimental design

### Physics

The light-key accumulation is calculated by weighting each stage derivative by its
holdup. The result is compared with the external feed-minus-product component flux.
At nominal steady state, the maximum absolute derivative is reported alongside the
composition range and monotonicity of the stage profile.

### Control

A feed light-key step from 0.50 to 0.62 is applied twice:

1. at fixed nominal reflux and boilup; and
2. with the paired top/bottom PID loops active.

Both simulations start at the same numerically converged nominal state. Metrics are
computed only after the disturbance. A 0.01 absolute composition-error band defines
settling.

### Numerical sensitivity

Closed-loop scenarios are repeated at several timesteps and compared with a
`dt = 0.05 min` reference. The final top and bottom product differences expose
discretization sensitivity without pretending that timestep agreement proves model
fidelity.

### Fault detection

A persistent +0.05 top-analyzer bias is injected at a known time. Detection delay,
pre-fault false-alarm fraction, and post-fault alarm fraction are reported. This is a
deterministic functional benchmark, not a claim about performance on noisy plant data.

### Soft-sensor generalization

The ridge soft sensor is fitted on 15 complete operating scenarios spanning five feed
compositions and three feed rates. Four off-grid feed-composition/feed-rate scenarios
are held out in full, preventing adjacent samples from one trajectory from appearing in
both fitting and evaluation data. The features use bottom, lower-tray, and upper-tray
temperature proxies plus measured operating inputs. Gaussian noise with a fixed seed and
`0.15 degC` standard deviation is added to the temperature features. The directly
invertible top-temperature proxy is deliberately excluded. Holdout RMSE and MAE are
compared with a constant predictor fitted on the training targets.

### Noisy multi-run fault detection

The robust fault suite tests `+0.030` and `-0.030` abrupt analyzer biases and a gradual
`+0.003 mole fraction/min` drift. Each family is repeated over 12 deterministic noise
seeds at analyzer noise standard deviation `0.004`. Separate no-fault runs quantify the
baseline alarm fraction. The report retains detection rate, median and 95th-percentile
detection delay, pre-fault false alarms, and post-fault alarm persistence.

## Acceptance gates

The automated suite requires:

- absolute light-key balance residual below `1e-12`;
- nominal steady-state maximum derivative below `3e-8`;
- physically bounded, monotonic nominal composition;
- improved final top and bottom error under paired PID control;
- improved top-composition IAE under paired PID control;
- final top and bottom product differences below `5e-4` across every tested
  timestep and below `5e-5` at `dt = 0.1 min`; and
- detection of the known analyzer bias without pre-fault false alarms;
- soft-sensor holdout RMSE below the constant-baseline RMSE;
- detection of every injected case in the seeded noisy fault suite; and
- zero alarms across the defined no-fault seeded-noise runs.

These thresholds are deliberately tied to the transparent model's stated assumptions.
They must be revisited—not silently reused—when Aspen or plant data becomes available.
