# Aspen Plus / Dynamics handoff

This document defines the validation work that requires licensed Aspen access. The
current repository does not include Aspen runs or Aspen-derived results.

## Before the licensed session

Already available in this repository:

- reproducible disturbance and fault definitions;
- open-model baseline trajectories;
- a stable CSV schema for time-series comparison;
- unit, integration, and API tests;
- documented model assumptions.

Prepare one campus-session folder containing:

- the cloned repository;
- a Python environment installed with the development extras;
- a blank location for sanitized exports under `artifacts/aspen/`;
- this checklist.

Do not commit university credentials, license-server details, machine names, or
proprietary Aspen installation files.

## Proposed Aspen case

Use a binary light-key/heavy-key system approved for coursework. Benzene/toluene is
a straightforward educational starting point. The final component pair and property
method should be selected for the chosen system and documented with the case.

Capture in `docs/aspen_case.md` after the run:

- Aspen product and version;
- components and property method;
- column block type and equilibrium/rate-based choice;
- number of stages and feed stage convention;
- feed flow, composition, pressure, temperature, and vapor fraction;
- condenser and reboiler specifications;
- pressure profile;
- convergence method;
- product flow and composition results.

## Steady-state validation

1. Converge the Aspen Plus case.
2. Export stage composition and temperature profiles.
3. Export feed, distillate, bottoms, reflux, and boilup streams.
4. Check total and component material-balance closure.
5. Map Aspen stage numbering explicitly to DistillTwin's bottom-to-top indexing.
6. Compare the open model and Aspen at the same normalized operating point.

Report at minimum:

- top and bottom light-key composition error;
- stage-profile RMSE;
- material-balance residual;
- any fitted relative-volatility or holdup values.

## Aspen Plus Dynamics validation

After the steady-state case is documented:

1. Convert to pressure-driven dynamics.
2. Size the reflux drum and column base or document inherited sizes.
3. Add pressure and inventory controllers before composition-quality loops.
4. Confirm a stable nominal trajectory.
5. Apply the repository's feed-composition and feed-rate steps.
6. Add analyzer bias and reduced valve effectiveness if the available license supports them.
7. Export time, product compositions, selected tray temperatures, controller outputs,
   and manipulated flows.

Compare rise time, settling time, peak deviation, integral absolute error, final
offset, and alarm timing.

## Automation adapter

The planned Windows adapter will use Aspen's documented automation interface from a
licensed machine. Keep the interface narrow:

~~~python
class SimulatorAdapter:
    def load_case(self, path: str) -> None: ...
    def set_inputs(self, values: dict[str, float]) -> None: ...
    def run(self) -> None: ...
    def read_outputs(self) -> dict[str, float]: ...
    def close(self) -> None: ...
~~~

An `OpenModelAdapter` should satisfy the same contract so CI does not require Aspen.
Aspen-specific tests should be marked as integration tests and skipped unless a
licensed runtime is explicitly available.

## Data contract

Sanitized transient exports should use these columns where available:

| Column | Meaning |
|---|---|
| time | elapsed simulation time in minutes |
| x_top | top-product light-key mole fraction |
| x_bottom | bottoms light-key mole fraction |
| temperature_top | top-stage or selected control-tray temperature |
| temperature_bottom | bottom-stage temperature |
| feed_rate | feed molar flow in documented units |
| feed_composition | feed light-key mole fraction |
| reflux_flow | reflux molar flow |
| boilup_flow | boilup molar flow or documented duty proxy |

Store generated data under `artifacts/aspen/`. Commit only data allowed by university
rules and remove licensed-file metadata or sensitive infrastructure details before
committing.

## Completion criteria

Change README language from "planned" to "validated" only after:

- a converged case exists;
- material balance closes within a documented tolerance;
- at least one transient has been exported;
- comparison metrics are reproducible from code;
- Aspen version, assumptions, and deviations are documented.
