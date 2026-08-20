# DistillTwin validation report

> Scope: Aspen-independent verification of the transparent reduced-order model.
> These results do not claim agreement with Aspen or plant data.

## Physics and steady state

| Check | Result |
|---|---:|
| Absolute light-key balance residual | 1.388e-17 |
| Maximum nominal steady-state derivative | 1.999e-08 |
| Minimum steady-state composition | 0.07480 |
| Maximum steady-state composition | 0.92520 |
| Monotonic composition profile | True |

## Disturbance-rejection benchmark

The benchmark applies the same feed light-key step from 0.50 to 0.62 to fixed-input
open-loop operation and to the paired composition PID loops.

| Mode | Variable | IAE | ISE | Peak error | Final error | Settling time |
|---|---|---:|---:|---:|---:|---:|
| open loop | top composition | 0.323078 | 0.005033 | 0.022357 | 0.022357 | 30.00 |
| paired PID | top composition | 0.237177 | 0.002491 | 0.012846 | 0.012838 | 30.00 |
| open loop | bottom composition | 0.489333 | 0.012315 | 0.038394 | 0.038394 | 30.00 |
| paired PID | bottom composition | 0.214695 | 0.001957 | 0.010609 | 0.009306 | 27.30 |

## RK4 timestep sensitivity

Final-product differences are measured against a dt =
0.050 min reference.

| dt (min) | Samples | Final top difference | Final bottom difference |
|---:|---:|---:|---:|
| 0.400 | 76 | 4.002e-05 | 6.227e-05 |
| 0.200 | 151 | 1.711e-05 | 2.645e-05 |
| 0.100 | 301 | 5.699e-06 | 8.778e-06 |

## Extended Kalman filter state estimation

The estimator reconstructs 8 stage compositions
from 4 signals: product compositions on
stages (7, 0) and temperature proxies on stages
(2, 5). The model-mismatch case uses a hidden plant
with relative volatility 2.20 and holdups 15% above the estimator model.

| Scenario | Obs. rank | Overall RMSE | Post-step RMSE | Transient RMSE | Peak state RMSE | Convergence delay | Converged |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 8 | 0.001913 | 0.000237 | 0.000134 | 0.012863 | 0.00 | True |
| unmeasured feed composition step | 8 | 0.015060 | 0.018259 | 0.010747 | 0.023438 | 16.00 | False |
| unmeasured feed rate step | 8 | 0.005990 | 0.006942 | 0.004174 | 0.012863 | 0.00 | True |
| sensor noise | 8 | 0.004345 | 0.000710 | 0.000405 | 0.026232 | 0.00 | True |
| model mismatch | 8 | 0.013775 | 0.016420 | 0.010960 | 0.020416 | 16.00 | False |

## Fault-detection benchmark

| Metric | Result |
|---|---:|
| Injected top-analyzer bias | 0.050 |
| Detected | True |
| Detection delay (min) | 0.400 |
| Pre-fault false-alarm fraction | 0.000% |
| Post-fault alarm fraction | 98.010% |

Generated deterministically by `distilltwin-validate`.
