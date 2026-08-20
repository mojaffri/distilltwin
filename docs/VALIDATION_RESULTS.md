# Validated reference results

These deterministic results were generated locally on 2026-08-20 from the feature
branch validation suite. The structured reference bundle is stored under
[`docs/reference/`](reference/) and CI recreates it as a workflow artifact.

> **Boundary:** this is Aspen-independent verification of the transparent reduced-order
> model. It does not claim agreement with Aspen or plant data.

## Physics and steady state

| Check | Result |
|---|---:|
| Absolute light-key balance residual | `1.388e-17` |
| Maximum nominal steady-state derivative | `1.999e-08` |
| Minimum steady-state composition | `0.07480` |
| Maximum steady-state composition | `0.92520` |
| Monotonic composition profile | Yes |

## Disturbance rejection

Both cases apply the same feed light-key step from 0.50 to 0.62. Open loop holds
reflux and boilup fixed; closed loop uses the paired composition PID controllers.

| Mode | Variable | IAE | ISE | Peak error | Final error | Settling time |
|---|---|---:|---:|---:|---:|---:|
| Open loop | Top composition | 0.323078 | 0.005033 | 0.022357 | 0.022357 | Not settled in 30 min |
| Paired PID | Top composition | 0.237177 | 0.002491 | 0.012846 | 0.012838 | Not settled in 30 min |
| Open loop | Bottom composition | 0.489333 | 0.012315 | 0.038394 | 0.038394 | Not settled in 30 min |
| Paired PID | Bottom composition | 0.214695 | 0.001957 | 0.010609 | 0.009306 | 27.30 min |

For this specified scenario, paired PID reduces top-composition IAE by **26.6%** and
bottom-composition IAE by **56.1%**. The top loop improves error substantially but
does not enter and remain inside the 0.01 absolute-error band within the 30-minute
post-disturbance window; that limitation is reported rather than hidden.

## RK4 timestep sensitivity

Final products are compared with a `dt = 0.05 min` reference.

| dt (min) | Samples | Final top difference | Final bottom difference |
|---:|---:|---:|---:|
| 0.400 | 76 | `4.002e-05` | `6.227e-05` |
| 0.200 | 151 | `1.711e-05` | `2.645e-05` |
| 0.100 | 301 | `5.699e-06` | `8.778e-06` |

Every tested final-product difference is below `6.3e-05`, and the `dt = 0.1 min`
case differs from the fine reference by less than `9e-06`.

## Extended Kalman filter

The EKF estimates eight stage compositions from top and bottom composition plus the
temperature proxies on stages 2 and 5. The local observability matrix at the nominal
point has rank 8. Feed disturbances are deliberately unmeasured in their named cases.

| Scenario | Overall RMSE | Post-step RMSE | Transient RMSE | Peak state RMSE | Convergence delay | Converged |
|---|---:|---:|---:|---:|---:|---:|
| Nominal | 0.001913 | 0.000237 | 0.000134 | 0.012863 | 0.00 min | Yes |
| Unmeasured feed-composition step | 0.015060 | 0.018259 | 0.010747 | 0.023438 | 16.00 min | No |
| Unmeasured feed-rate step | 0.005990 | 0.006942 | 0.004174 | 0.012863 | 0.00 min | Yes |
| Sensor noise at 3x reference standard deviations | 0.004345 | 0.000710 | 0.000405 | 0.026232 | 0.00 min | Yes |
| Model mismatch and unmeasured feed-composition step | 0.013775 | 0.016420 | 0.010960 | 0.020416 | 16.00 min | No |

The mismatch case uses plant relative volatility `2.20` versus estimator value `2.40`
and plant holdups 15% above the estimator model. Convergence requires the instantaneous
eight-state RMSE to remain at or below `0.02` for the rest of the run. The unmeasured
feed-composition and mismatch cases do not meet that definition. Per-stage values are
stored in [`reference/state_estimation_benchmark.csv`](reference/state_estimation_benchmark.csv).

## Known-fault benchmark

| Metric | Result |
|---|---:|
| Injected top-analyzer bias | +0.050 |
| Detected | Yes |
| Detection delay | 0.400 min |
| Pre-fault false-alarm fraction | 0.000% |
| Post-fault alarm fraction | 98.010% |

The top-analyzer residual uses a reference EKF corrected from the bottom composition
and two selected tray temperatures. It does not use the hidden top state. This
deterministic injection verifies functional behavior; it is not a statistical claim
about noisy industrial data.

## Software evidence from the same commit

- 34 automated tests passed locally on Python 3.12.
- Measured line coverage: **92.28%**, above the enforced 90% gate.
- Ruff and strict Mypy passed.
- The Streamlit application completed an AppTest smoke run and rendered the EKF table.
- Docker build and container smoke results remain those of the preceding `main` commit
  until this branch runs in GitHub Actions.
- Five validation artifacts are generated: Markdown, JSON, and three CSVs.

Reproduce these results with:

~~~bash
distilltwin-validate --output validation-report
~~~
