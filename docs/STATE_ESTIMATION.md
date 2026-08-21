# State-estimation design and benchmark

## Estimator structure

The estimator is a discrete extended Kalman filter (EKF) around the same nonlinear
stage-balance equations used by the control-oriented twin. For one integration step,

```text
x[k+1] = F_RK4(x[k], u[k]) + w[k]
z[k]   = h(x[k]) + v[k]
```

where `F_RK4` is the fourth-order Runge-Kutta transition, `w` is the configured
process uncertainty, and `v` is measurement noise. The implementation propagates the
exact continuous stage-balance Jacobian through the RK4 stages. The covariance update
uses Joseph form and applies a small eigenvalue floor after symmetrization.

The code is in [`src/distilltwin/estimation.py`](../src/distilltwin/estimation.py).
The analytical RK4 transition Jacobian is checked against an independent centered
finite-difference calculation in
[`tests/test_estimation.py`](../tests/test_estimation.py).

## Measurement boundary

Stage indices run from the reboiler (`0`) to the total condenser (`7`). The reference
benchmark measures four signals:

- top composition, stage `7`;
- bottom composition, stage `0`;
- temperature proxy, stage `2`;
- temperature proxy, stage `5`.

The other four stage compositions remain hidden from the estimator. Composition and
temperature noise standard deviations are configurable. The reference settings are
`0.002` mole fraction and `0.08 degC`, with a fixed random seed for reproducibility.
The temperature signal remains the model's documented composition-based proxy; it is
not an energy-balance temperature prediction.

The local discrete observability matrix at the nominal operating point has rank `8`,
equal to the state dimension. This local result does not establish global nonlinear
observability over every operating condition.

## Hidden plant and mismatch

[`src/distilltwin/estimation_validation.py`](../src/distilltwin/estimation_validation.py)
constructs separate plant and estimator model instances. The estimator receives
measurements generated from the plant but never receives the plant state vector.

The named feed-composition and feed-rate cases deliberately leave the corresponding
disturbance out of the estimator input. The mismatch case combines an unmeasured feed
composition step with:

- plant relative volatility `2.20` versus estimator value `2.40`;
- plant tray, condenser, and reboiler holdups `15%` above estimator values.

This mismatch is controlled and reproducible. It is not calibrated to Aspen or plant
data.

## Metrics and convergence

Each case reports per-stage RMSE, overall RMSE, post-disturbance RMSE, RMSE during the
first five minutes after the disturbance, peak instantaneous state RMSE, and
convergence. Convergence means that the instantaneous RMSE across all eight states is
at or below `0.02` for every remaining sample in the evaluation window.

The stored reference results are in
[`docs/reference/state_estimation_benchmark.csv`](reference/state_estimation_benchmark.csv)
and [`docs/VALIDATION_RESULTS.md`](VALIDATION_RESULTS.md). Recreate the complete bundle
with:

```bash
distilltwin-validate --output validation-report
```

The unmeasured feed-composition and model-mismatch cases do not meet the convergence
definition inside the 16-minute post-disturbance window. That result limits use of the
current EKF when important feed properties or model parameters drift without separate
estimation. Online disturbance or parameter estimation is the next appropriate
extension before output-feedback MPC is evaluated.
