"""Interactive process-control lab for the open DistillTwin model."""

from __future__ import annotations

import streamlit as st

from distilltwin.scenarios import Scenario, ScenarioRunner

st.set_page_config(page_title="DistillTwin Control Room", page_icon="🏭", layout="wide")
st.title("DistillTwin Control Room")
st.caption(
    "Explore closed-loop disturbance rejection and equipment/sensor faults in a "
    "transparent dynamic distillation model."
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

top_error = float((frame["x_top"] - frame["top_setpoint"]).abs().max())
bottom_error = float((frame["x_bottom"] - frame["bottom_setpoint"]).abs().max())
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
    st.warning(f"Sensor residual alarm first crossed its threshold at t = {first_alarm:.1f} min.")
else:
    st.success("No sensor residual alarm in this scenario.")

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

