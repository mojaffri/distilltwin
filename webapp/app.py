"""Interactive process-control and validation lab for DistillTwin."""

from __future__ import annotations

from inspect import signature

import pandas as pd
import streamlit as st

from distilltwin.scenarios import Scenario, ScenarioRunner
from distilltwin.validation import generate_validation_report, render_markdown

TEAL = "#0F766E"
BLUE = "#2563A6"
AMBER = "#C17B22"
SLATE = "#64748B"

st.set_page_config(
    page_title="DistillTwin | Process control lab",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="auto",
)


def apply_visual_system() -> None:
    """Apply a restrained, engineering-focused visual system."""
    st.markdown(
        """
        <style>
        :root {
            --ink: #132A3A;
            --muted: #5F6F7A;
            --line: #D7E0E5;
            --teal: #0F766E;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 78% 0%, rgba(15, 118, 110, 0.08), transparent 28rem),
                linear-gradient(180deg, #F8FAFA 0%, #F3F7F7 100%);
            color: var(--ink);
        }

        [data-testid="stHeader"] { background: transparent; }

        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            background: #102A32;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * { color: #E8F0F1; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #AFC2C5; }
        [data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.12); }

        .dt-hero {
            position: relative;
            overflow: hidden;
            padding: 2.1rem 2.25rem 1.9rem;
            border: 1px solid #D7E0E5;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.88);
            box-shadow: 0 18px 55px rgba(19, 42, 58, 0.08);
            margin-bottom: 1.4rem;
        }

        .dt-hero::after {
            content: "";
            position: absolute;
            width: 360px;
            height: 360px;
            right: -150px;
            top: -210px;
            border-radius: 50%;
            border: 48px solid rgba(15, 118, 110, 0.08);
        }

        .dt-eyebrow {
            color: var(--teal);
            font-size: 0.73rem;
            font-weight: 750;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
        }

        .dt-hero h1 {
            color: var(--ink);
            font-size: clamp(2.25rem, 5vw, 4.25rem);
            line-height: 0.98;
            letter-spacing: -0.055em;
            margin: 0;
        }

        .dt-hero p {
            color: var(--muted);
            max-width: 790px;
            font-size: 1.05rem;
            line-height: 1.65;
            margin: 1rem 0 1.25rem;
        }

        .dt-tags { display: flex; flex-wrap: wrap; gap: 0.55rem; }
        .dt-tag {
            border: 1px solid #C9D8D7;
            border-radius: 999px;
            background: #F4F9F8;
            color: #28524F;
            font-size: 0.76rem;
            font-weight: 650;
            letter-spacing: 0.015em;
            padding: 0.38rem 0.72rem;
        }

        .dt-section {
            margin: 1.45rem 0 0.65rem;
            color: var(--ink);
            font-size: 0.75rem;
            font-weight: 750;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .dt-note {
            border: 1px solid #D7E0E5;
            border-left: 4px solid var(--teal);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.76);
            color: #4E616D;
            line-height: 1.55;
            padding: 0.9rem 1rem;
            margin: 0.3rem 0 1rem;
        }

        [data-testid="stMetric"] {
            min-height: 118px;
            border: 1px solid #D7E0E5;
            border-radius: 13px;
            background: rgba(255, 255, 255, 0.9);
            box-shadow: 0 8px 24px rgba(19, 42, 58, 0.045);
            padding: 1rem 1.05rem;
        }

        [data-testid="stMetricLabel"] p {
            color: #657680;
            font-size: 0.73rem;
            font-weight: 700;
            letter-spacing: 0.055em;
            text-transform: uppercase;
        }

        [data-testid="stMetricValue"] { color: var(--ink); }

        [data-baseweb="tab-list"] {
            gap: 1.6rem;
            border-bottom: 1px solid #D7E0E5;
        }

        [data-baseweb="tab"] {
            height: 3.4rem;
            padding-left: 0;
            padding-right: 0;
            color: #64747D;
            font-weight: 650;
        }

        [aria-selected="true"][data-baseweb="tab"] { color: var(--teal); }

        [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] {
            border: 1px solid #D7E0E5;
            border-radius: 12px;
            overflow: hidden;
            background: #FFFFFF;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 9px;
            font-weight: 700;
            min-height: 2.8rem;
        }

        @media (max-width: 700px) {
            .block-container { padding-top: 1.1rem; }
            .dt-hero { padding: 1.5rem 1.25rem; border-radius: 14px; }
            .dt-hero p { font-size: 0.96rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(f'<div class="dt-section">{text}</div>', unsafe_allow_html=True)


def trend_chart(
    data: pd.DataFrame,
    columns: list[str],
    colors: list[str],
    *,
    height: int = 320,
) -> None:
    width_option: dict[str, object]
    if "width" in signature(st.line_chart).parameters:
        width_option = {"width": "stretch"}
    else:
        width_option = {"use_container_width": True}
    st.line_chart(
        data.set_index("time")[columns],
        color=colors,
        height=height,
        **width_option,
    )


@st.cache_data(show_spinner=False)
def run_scenario(scenario: Scenario) -> pd.DataFrame:
    return ScenarioRunner().run(scenario)


apply_visual_system()

st.markdown(
    """
    <section class="dt-hero">
        <div class="dt-eyebrow">Process systems engineering · interactive model</div>
        <h1>DistillTwin</h1>
        <p>
            An eight-stage binary distillation lab for closed-loop control, partial-measurement
            state estimation, and known-fault studies—paired with deterministic validation.
        </p>
        <div class="dt-tags">
            <span class="dt-tag">8 equilibrium stages</span>
            <span class="dt-tag">Paired PID loops</span>
            <span class="dt-tag">Extended Kalman filter</span>
            <span class="dt-tag">92%+ line coverage</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Operating case")
    st.caption("Adjust the disturbance and fault scenario. The model reruns deterministically.")
    st.divider()
    duration = st.slider("Duration (min)", 20.0, 120.0, 60.0, 5.0)
    disturbance_at = st.slider(
        "Disturbance time (min)", 0.0, duration, min(20.0, duration), 1.0
    )
    feed_composition = st.slider("Post-step feed light-key fraction", 0.20, 0.80, 0.58, 0.01)
    feed_rate = st.slider("Post-step feed rate", 0.60, 1.40, 1.00, 0.05)
    st.divider()
    st.markdown("#### Fault injection")
    sensor_bias = st.slider("Top analyzer bias", -0.10, 0.10, 0.00, 0.005)
    valve_effectiveness = st.slider("Reflux-valve effectiveness", 0.50, 1.00, 1.00, 0.01)
    st.caption("Nominal analyzer bias is 0.00; nominal valve effectiveness is 1.00.")

scenario = Scenario(
    duration=duration,
    disturbance_at=disturbance_at,
    feed_composition_after=feed_composition,
    feed_rate_after=feed_rate,
    top_sensor_bias_after=sensor_bias,
    reflux_effectiveness_after=valve_effectiveness,
)
frame = run_scenario(scenario)

control_tab, validation_tab = st.tabs(["Live scenario", "Validation evidence"])

with control_tab:
    top_error = float((frame["x_top"] - frame["top_setpoint"]).abs().max())
    alarm_count = int(frame["sensor_alarm"].sum())
    final_top = float(frame["x_top"].iloc[-1])
    final_bottom = float(frame["x_bottom"].iloc[-1])
    final_top_error = final_top - float(frame["top_setpoint"].iloc[-1])
    final_bottom_error = final_bottom - float(frame["bottom_setpoint"].iloc[-1])

    section_label("Run summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Final top purity",
        f"{final_top:.4f}",
        f"{final_top_error:+.4f} vs setpoint",
        delta_color="off",
    )
    col2.metric(
        "Final bottom light key",
        f"{final_bottom:.4f}",
        f"{final_bottom_error:+.4f} vs setpoint",
        delta_color="off",
    )
    col3.metric("Peak top error", f"{top_error:.4f}")
    col4.metric("Residual alarms", f"{alarm_count}")

    section_label("Composition response")
    trend_chart(
        frame,
        ["x_top", "top_setpoint", "x_bottom", "bottom_setpoint"],
        [TEAL, SLATE, BLUE, AMBER],
        height=360,
    )

    left, right = st.columns(2)
    with left:
        section_label("Manipulated variables")
        trend_chart(frame, ["reflux_flow", "boilup_flow"], [TEAL, AMBER], height=285)
    with right:
        section_label("Temperature signals")
        trend_chart(
            frame,
            ["temperature_top", "temperature_bottom"],
            [BLUE, AMBER],
            height=285,
        )

    section_label("Analyzer residual")
    trend_chart(frame, ["sensor_residual_ewma"], [TEAL], height=245)
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
    section_label("Reproducible benchmark bundle")
    st.markdown(
        """
        <div class="dt-note">
            The validation suite checks conservation, stationarity, numerical sensitivity,
            paired control performance, partial-measurement estimation, and known-fault
            detection inside the reduced-order model boundary. It does not claim agreement
            with Aspen or plant data.
        </div>
        """,
        unsafe_allow_html=True,
    )

    run_validation = st.button("Run validation benchmarks", type="primary")
    if not run_validation:
        st.caption(
            "The stored reference tables are committed under docs/reference/. Run here to "
            "recompute them in this session."
        )
    else:
        report = cached_validation_report()
        physics = report.physics
        fault = report.fault_detection
        top_open = report.control.open_loop_top
        top_pid = report.control.closed_loop_top
        iae_improvement = 100.0 * (1.0 - top_pid.iae / top_open.iae)

        section_label("Acceptance indicators")
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

        section_label("Open-loop versus paired PID")
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

        section_label("EKF state-estimation benchmark")
        st.caption(
            "Eight stage compositions reconstructed from top/bottom composition and two "
            "selected temperature signals. Feed disturbances are unmeasured in their named "
            "cases; the mismatch case changes hidden-plant volatility and holdup."
        )
        estimation_frame = pd.DataFrame(
            [
                {
                    "scenario": case.scenario.name,
                    "observability_rank": case.observability_rank,
                    "overall_rmse": case.metrics.overall_rmse,
                    "post_disturbance_rmse": case.metrics.post_disturbance_rmse,
                    "transient_rmse": case.metrics.transient_rmse,
                    "peak_state_rmse": case.metrics.peak_state_rmse,
                    "convergence_delay": case.metrics.convergence_delay,
                    "converged": case.metrics.converged,
                }
                for case in report.state_estimation.cases
            ]
        )
        st.dataframe(
            estimation_frame.style.format(
                {
                    "overall_rmse": "{:.6f}",
                    "post_disturbance_rmse": "{:.6f}",
                    "transient_rmse": "{:.6f}",
                    "peak_state_rmse": "{:.6f}",
                    "convergence_delay": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        left, right = st.columns(2)
        with left:
            section_label("RK4 timestep sensitivity")
            timestep_frame = pd.DataFrame([case.to_dict() for case in report.timestep_cases])
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
            section_label("Known-fault benchmark")
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

with st.expander("Model scope and validation boundary"):
    st.markdown(
        """
        This is a control-oriented binary equilibrium-stage model using constant relative
        volatility and constant molar overflow. It is useful for dynamics, controls, fault
        injection, analytics, APIs, and software testing. It is **not** a claim of Aspen
        Plus fidelity. The repository documents the planned Aspen Plus/Dynamics calibration
        and validation workflow separately.
        """
    )
