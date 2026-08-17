"""Interactive process-control and validation lab for DistillTwin."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from distilltwin.scenarios import Scenario, ScenarioRunner
from distilltwin.validation import generate_validation_report, render_markdown

st.set_page_config(page_title="DistillTwin Engineering Lab", page_icon="🏭", layout="wide")
st.title("DistillTwin Engineering Lab")
st.caption(
    "Explore closed-loop disturbance rejection, equipment and sensor faults, and "
    "reproducible engineering validation in a transparent dynamic distillation model."
)

with st.sidebar:
    st.header("Scenario")
    duration = st.slider("Duration (min)", 20.0, 120.0, 60.0, 5.0)
    disturbance_at = st.slider(
        "Disturbance time (min)", 0.0, duration, min(20.0, duration), 1.0
    )
    feed_composition = st.slider("Post-step feed light-key fraction", 0.20, 0.80, 0.58, 0.01)
    feed_rate = st.slider("Post-step feed rate", 0.60, 1.40, 1.00, 0.05)
    sensor_bias = st.slider("Top analyzer bias", -0.10, 0.10, 0.00, 0.005)
    valve_effectiveness = st.slider("Reflux-valve effectiveness", 0.50, 1.00, 1.00, 0.01)

scenario = Scenario(
    duration=duration,
    disturbance_at=disturbance_at,
    feed_composition_after=feed_composition,
    feed_rate_after=feed_rate,
    top_sensor_bias_after=sensor_bias,
    reflux_effectiveness_after=valve_effectiveness,
)
frame = ScenarioRunner().run(scenario)

control_tab, validation_tab = st.tabs(["Control room", "Validation lab"])

with control_tab:
    top_error = float((frame["x_top"] - frame["top_setpoint"]).abs().max())
    alarm_count = int(frame["sensor_alarm"].sum())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final top purity", f"{frame['x_top'].iloc[-1]:.4f}")
    col2.metric("Final bottom light key", f"{frame['x_bottom'].iloc[-1]:.4f}")
    col3.metric("Peak |top error|", f"{top_error:.4f}")
    col4.metric("Alarm samples", f"{alarm_count}")

    st.subheader("Product composition and setpoints")
    st.line_chart(
        frame.set_index("time")[["x_top", "top_setpoint", "x_bottom", "bottom_setpoint"]]
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Manipulated variables")
        st.line_chart(frame.set_index("time")[["reflux_flow", "boilup_flow"]])
    with right:
        st.subheader("Temperature signals")
        st.line_chart(frame.set_index("time")[["temperature_top", "temperature_bottom"]])

    st.subheader("Fault residual")
    st.line_chart(frame.set_index("time")[["sensor_residual_ewma"]])
    if alarm_count:
        first_alarm = float(frame.loc[frame["sensor_alarm"], "time"].iloc[0])
        st.warning(
            f"Sensor residual alarm first crossed its threshold at t = {first_alarm:.1f} min."
        )
    else:
        st.success("No sensor residual alarm in this scenario.")


@st.cache_data(show_spinner="Running deterministic validation benchmarks...")
def cached_validation_report() -> object:
    return generate_validation_report()


with validation_tab:
    report = cached_validation_report()
    physics = report.physics
    fault = report.fault_detection
    top_open = report.control.open_loop_top
    top_pid = report.control.closed_loop_top
    iae_improvement = 100.0 * (1.0 - top_pid.iae / top_open.iae)

    st.subheader("Aspen-independent evidence")
    st.info(
        "This lab verifies conservation, stationarity, numerical sensitivity, control "
        "performance, and known-fault detection inside the reduced-order assumptions. "
        "It does not claim Aspen or plant-data agreement."
    )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric(
        "Balance residual",
        f"{physics.material_balance_absolute_residual:.2e}",
        help="Absolute discrepancy between total light-key accumulation and boundary flux.",
    )
    metric2.metric(
        "Steady-state residual",
        f"{physics.steady_state_max_derivative:.2e}",
        help="Maximum absolute stage derivative at the nominal numerical steady state.",
    )
    metric3.metric(
        "Top IAE reduction",
        f"{iae_improvement:.1f}%",
        help="Paired PID versus fixed-input open-loop response to the same feed step.",
    )
    metric4.metric(
        "Bias detection delay",
        f"{fault.detection_delay:.2f} min",
        help="Delay after injecting a persistent +0.05 top-analyzer bias.",
    )

    st.subheader("Open-loop versus paired PID")
    control_frame = pd.DataFrame(report.control.rows())
    st.dataframe(
        control_frame.style.format(
            {
                "iae": "{:.6f}",
                "ise": "{:.6f}",
                "peak_absolute_error": "{:.6f}",
                "final_absolute_error": "{:.6f}",
                "settling_time": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(2)
    with left:
        st.subheader("RK4 timestep sensitivity")
        timestep_frame = pd.DataFrame(
            [case.to_dict() for case in report.timestep_cases]
        )
        st.dataframe(
            timestep_frame.style.format(
                {
                    "dt": "{:.3f}",
                    "final_top_absolute_difference": "{:.3e}",
                    "final_bottom_absolute_difference": "{:.3e}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Final-product differences versus a dt = "
            f"{report.timestep_reference_dt:.3f} min reference."
        )
    with right:
        st.subheader("Known-fault benchmark")
        st.write(
            {
                "Injected analyzer bias": f"{fault.injected_bias:+.3f}",
                "Detected": fault.detected,
                "Detection delay": f"{fault.detection_delay:.3f} min",
                "Pre-fault false alarms": f"{fault.false_alarm_fraction:.2%}",
                "Post-fault alarm fraction": f"{fault.post_fault_alarm_fraction:.2%}",
            }
        )

    st.download_button(
        "Download validation report",
        data=render_markdown(report),
        file_name="DISTILLTWIN_VALIDATION_REPORT.md",
        mime="text/markdown",
    )

with st.expander("What this model is—and is not"):
    st.markdown(
        """
        This is a control-oriented binary equilibrium-stage model using constant relative
        volatility and constant molar overflow. It is useful for dynamics, controls, fault
        injection, analytics, APIs, and software testing. It is **not** a claim of Aspen
        Plus fidelity. The repository documents the planned Aspen Plus/Dynamics calibration
        and validation workflow separately.
        """
    )
