import altair as alt
import pandas as pd
import streamlit as st

from staffing import Inputs, blended_plan, dedicated_plan, erlang_c_agents, inbound_curve

st.set_page_config(page_title="ECC Staffing Simulator", layout="wide")
st.title("📞 ECC Staffing Simulator")
st.caption("Daily FTE requirement using exact Erlang A (with caller abandonment). "
           "Compares a dedicated inbound + outbound team with a blended team.")

# ---------------------------------------------------------------- inputs
with st.sidebar.form("inputs"):
    st.header("Inbound demand")
    calls_per_day = st.number_input("Calls per day", min_value=1, value=250)
    aht_sec = st.number_input("Average handle time, incl. ACW (sec)", min_value=1, value=600)
    patience_sec = st.number_input(
        "Average caller patience (sec)", min_value=5, value=150,
        help="Average time a caller waits before hanging up. Estimate from phone data as "
             "total wait time of ALL calls ÷ number of abandoned calls.")

    st.header("Outbound demand")
    ob_tasks = st.number_input("Outbound tasks per day", min_value=0, value=90)
    ob_aht = st.number_input("Average time per outbound task (sec)", min_value=1, value=300)
    ob_target = st.slider("Outbound tasks completed same day (%)", 50, 100, 98,
                          help="Used for the blended team only.")

    st.header("Goals")
    target_sl = st.slider("Service level (%)", 50, 100, 80)
    sl_threshold = st.number_input("Service level threshold (sec)", min_value=5, value=30, step=5)
    target_ar = st.slider("Answer rate (%)", 50, 100, 95)
    max_occ = st.slider("Maximum occupancy (%)", 50, 100, 85,
                        help="Cap on the share of on-floor time agents spend working, to limit burnout.")

    st.header("Schedule")
    hours_open = st.number_input("Hours open per day", min_value=1.0, max_value=24.0, value=9.0, step=0.5)
    shift_hours = st.number_input("Paid hours per agent shift", min_value=1.0, max_value=12.0, value=8.0, step=0.5)
    shrinkage = st.slider("Shrinkage (%)", 0, 60, 20,
                          help="Paid time not available for work: breaks, meetings, training, PTO.")

    submitted = st.form_submit_button("Calculate", type="primary", width="stretch")

x = Inputs(calls_per_day, aht_sec, ob_tasks, ob_aht, hours_open, shift_hours,
           target_sl / 100, sl_threshold, target_ar / 100, patience_sec,
           shrinkage / 100, max_occ / 100, ob_target / 100)


@st.cache_data(show_spinner=False)
def run_blended(key: tuple, start: int):
    return blended_plan(Inputs(*key), start)


ded = dedicated_plan(x)
if ded.inbound is None:
    st.error("No staffing level up to 1,000 agents meets these goals. Check the inputs.")
    st.stop()

with st.spinner("Simulating the blended team (300 days)…"):
    key = tuple(x.__dict__.values())
    bl = run_blended(key, ded.inbound.agents)

# ---------------------------------------------------------------- summary
tab_sum, tab_in, tab_why, tab_how = st.tabs(
    ["Staffing summary", "Inbound detail", "Why Erlang A", "Method and assumptions"])

with tab_sum:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Option 1: Dedicated teams")
        st.metric("Total FTE", f"{ded.total_fte:.1f}")
        a, b = st.columns(2)
        a.metric("Inbound FTE", f"{ded.inbound_fte:.1f}",
                 help=f"{ded.inbound.agents} agents on the phones every open hour")
        b.metric("Outbound FTE", f"{ded.outbound_fte:.1f}",
                 help=f"{x.ob_work_hours:.1f} hours of outbound work per day")
        m = ded.inbound
        st.write(f"Inbound results with **{m.agents} agents on floor**: service level "
                 f"{m.service_level:.1%}, answer rate {m.answer_rate:.1%}, "
                 f"occupancy {m.occupancy:.0%}, average wait {m.avg_wait_sec:.0f} s.")
    with c2:
        st.subheader("Option 2: Blended team")
        if bl.agents is None:
            st.warning("No blended team within 15 agents of the inbound requirement met all goals.")
        else:
            s = bl.sim
            st.metric("Total FTE", f"{bl.fte:.1f}",
                      delta=f"{bl.fte - ded.total_fte:+.1f} vs dedicated", delta_color="inverse")
            a, b = st.columns(2)
            a.metric("Agents on floor", bl.agents)
            b.metric("Agents held for calls", bl.reserve,
                     help="Outbound work starts only when more than this many agents would stay idle.")
            st.write(f"Simulated results: service level {s['service_level']:.1%}, answer rate "
                     f"{s['answer_rate']:.1%}, outbound completed {s['outbound_done']:.1%}, "
                     f"occupancy {s['occupancy']:.0%}. On the worst 10% of days service level "
                     f"falls to {s['sl_p10']:.0%}.")
    st.info("Blended agents work outbound tasks in the idle time between calls, so outbound "
            "work is partly absorbed by the inbound staffing. Calls always take priority.")

# ---------------------------------------------------------------- inbound detail
with tab_in:
    n0 = ded.inbound.agents
    df = pd.DataFrame(inbound_curve(x, n0 - 4, n0 + 5))
    long = df.melt("Agents on floor", ["Service level (Erlang A)", "Answer rate (Erlang A)"],
                   var_name="Measure", value_name="Value")
    base = alt.Chart(long).encode(
        x=alt.X("Agents on floor:O", title="Agents on floor", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Value:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("Measure:N", legend=alt.Legend(orient="top", title=None),
                        scale=alt.Scale(domain=["Service level (Erlang A)", "Answer rate (Erlang A)"],
                                        range=["#2a78d6", "#eb6834"])),
        tooltip=["Agents on floor", "Measure", alt.Tooltip("Value:Q", format=".1%")],
    )
    targets = pd.DataFrame({"y": [x.target_sl, x.target_answer_rate]})
    rules = alt.Chart(targets).mark_rule(strokeDash=[4, 4], color="#888").encode(y="y:Q")
    st.altair_chart((base.mark_line(strokeWidth=2) + base.mark_point(size=64, filled=True) + rules)
                    .properties(height=320), width="stretch")
    st.caption("Dashed lines show the service level and answer rate goals.")
    show = df.copy()
    for col in ["Service level (Erlang A)", "Answer rate (Erlang A)", "Service level (Erlang C)", "Occupancy"]:
        show[col] = show[col].map(lambda v: "unstable" if pd.isna(v) else f"{v:.1%}")
    show["Avg wait (s)"] = show["Avg wait (s)"].round(0)
    show["Rostered FTE"] = show["Rostered FTE"].round(1)
    st.dataframe(show, hide_index=True, width="stretch")

# ---------------------------------------------------------------- why Erlang A
with tab_why:
    nc = erlang_c_agents(x)
    st.markdown(f"""
**Erlang C assumes every caller waits forever.** Real callers hang up. Because of that, Erlang C
- overstates how long the queue gets and how many callers wait,
- cannot predict answer rate or abandonment at all, so it cannot staff to an answer-rate goal,
- becomes unusable (infinite wait) whenever calls exceed agent capacity.

**Erlang A adds caller patience.** Callers who hang up shorten the queue for everyone else, so
Erlang A gives a realistic service level *and* the answer rate. With infinite patience it
reduces exactly to Erlang C.

For the current inputs: Erlang C needs **{nc if nc else "n/a"}** agents to hit the service level goal
(and cannot check answer rate). Erlang A needs **{ded.inbound.agents}** agents to hit both goals.
The table on the Inbound detail tab shows both service levels side by side.
""")

# ---------------------------------------------------------------- method
with tab_how:
    st.markdown(f"""
**Inbound (both options).** Calls per hour = calls per day ÷ hours open (volume assumed flat through
the day). The exact Erlang A (M/M/n+M) model gives service level, answer rate, occupancy and
average wait for each headcount. The required headcount is the smallest that meets the service
level, answer rate and maximum occupancy goals. Service level counts calls answered within the
threshold as a share of all offered calls, so early hang-ups count against it.

**Converting agents to FTE.** FTE = agents on floor × (hours open ÷ shift hours) ÷ (1 − shrinkage).
Currently {x.hours_open:g} ÷ {x.shift_hours:g} and {x.shrinkage:.0%} shrinkage.

**Dedicated outbound.** FTE = outbound work hours ÷ (shift hours × (1 − shrinkage) × max occupancy).

**Blended team.** A day-long simulation (300 simulated days) in which all agents take calls first
and work outbound tasks when no call is waiting and more than a set number of agents would remain
idle. The app searches for the smallest team and reserve setting (0, 1 or 2) that meets every goal.
Outbound tasks are not interrupted once started, so calls can wait behind them. This cost is
captured by the simulation.

**Assumptions.** Random (Poisson) call arrivals, exponentially distributed handle time and patience,
flat volume across the day, and outbound tasks arriving evenly across the day.
""")
