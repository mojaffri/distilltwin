# Validated reference results

These deterministic results were generated in GitHub Actions on 2026-08-17 from the
1.0.0 validation suite. The full Markdown, JSON, and CSV bundle is also retained as a
workflow artifact for each successful run.

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

## Known-fault benchmark

| Metric | Result |
|---|---:|
| Injected top-analyzer bias | +0.050 |
| Detected | Yes |
| Detection delay | 0.400 min |
| Pre-fault false-alarm fraction | 0.000% |
| Post-fault alarm fraction | 98.010% |

This deterministic injection verifies functional behavior. It is not a statistical
claim about noisy industrial data.

## Software evidence from the same commit

- 23 automated tests passed on Python 3.11 and 3.12.
- Measured line coverage: **93.18%**, above the enforced 90% gate.
- Ruff and strict Mypy passed.
- The production Docker image built successfully.
- CI launched the image and received a successful response from the real `/health`
  endpoint.
- Four validation artifacts were generated and uploaded: Markdown, JSON, and two CSVs.

Reproduce these results with:

~~~bash
distilltwin-validate --output validation-report
~~~
