import streamlit as st
import math

# --- Erlang A Function (Revised for Answer Rate and Accuracy) ---
def erlang_a_fte(
    calls_per_hour,
    aht_sec,
    target_sla=0.80,
    sla_threshold_sec=30,
    target_answer_rate=0.95,
    avg_patience_sec=120, # Average time a customer will wait before abandoning
    max_agents=100,
    shrinkage=0.30
):
    """
    Calculates the required number of agents using the Erlang A formula.

    This version solves for the number of agents (N) needed to simultaneously
    meet a Service Level (SL) target and an Answer Rate target.
    """
    lambda_per_sec = calls_per_hour / 3600
    mu = 1 / aht_sec
    theta = 1 / avg_patience_sec  # Abandonment rate (alpha in some texts)

    # Iterate through the number of agents to find the minimum required
    for n in range(1, max_agents):
        rho = lambda_per_sec / (n * mu)  # Traffic intensity

        # System must be stable (traffic intensity < 1)
        if rho >= 1:
            continue

        # --- Erlang C base calculation ---
        erlang_b = ((lambda_per_sec / mu)**n / math.factorial(n))
        sum_erlang_b = sum(((lambda_per_sec / mu)**k / math.factorial(k)) for k in range(n))
        p0 = 1 / (sum_erlang_b + erlang_b / (1 - rho))
        
        # Probability of Waiting (Pw), using the Erlang C formula
        pw = (erlang_b / (1 - rho)) * p0

        # --- Check against targets ---
        
        # 1. Calculate Service Level (SL)
        # SL = 1 - P(wait > threshold) = 1 - Pw * e^(-(N*µ - λ)*t)
        exponent_sl = -((n * mu) - lambda_per_sec) * sla_threshold_sec
        service_level = 1 - (pw * math.exp(exponent_sl))

        # 2. Calculate Answer Rate
        # Answer Rate = 1 - Abandonment Rate
        # Abandonment Rate = Pw * (θ / (N*µ + θ - λ)) -> this can be unstable
        # A more stable approximation: Abandonment Rate = Pw * (θ / (N*µ + θ))
        prob_abandon_given_wait = theta / (n * mu + theta)
        abandonment_rate = pw * prob_abandon_given_wait
        answer_rate = 1 - abandonment_rate

        # 3. Check if both conditions are met
        if service_level >= target_sla and answer_rate >= target_answer_rate:
            # Return the number of agents, adjusted for shrinkage
            return math.ceil(n / (1 - shrinkage))

    return None # Return None if no solution is found within max_agents

# --- App Constants ---
hours_of_operation = 9      # Total hours the call center is open
agent_work_hours = 8        # Hours an agent works in a shift
# This ratio calculates the extra staff needed to cover all open hours with shorter shifts
coverage_factor = hours_of_operation / agent_work_hours

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("📞 ECC Staffing Simulator")
st.write("This tool helps determine the number of FTEs needed to staff an ECC Pod based on the Erlang model, which accounts for caller abandonment.")

col1, = st.columns(1)

with col1:
    st.divider()
    st.header("Inbound Demand")
    calls_per_day = st.number_input("Total Calls per Day", min_value=1, value=250, help="Total Number of Inbound Calls expected for a day")
    aht_sec = st.number_input("Average Handle Time (seconds)", min_value=1, value=600,help="Average Handle Time including ACW.")

    st.divider()
    st.header("Outbound Demand")
    outbound_referrals_per_day = st.number_input("Outbound Tasks or Referrals per Day", min_value=0, value=90)
    avg_time_per_referral_sec = st.number_input("Average Time per Outbound Task (seconds)", min_value=1, value=300)

    st.divider()
    st.header("Goals and Shrinkage")
    target_sla = st.slider("Target Service Level (%)", min_value=50, max_value=100, value=80, step=1, help="The percentage of calls to be answered within the threshold.")
    sla_threshold_sec = st.number_input("Service Level Threshold (seconds)", value=30, step =5)
    target_answer_rate = st.slider("Target Answer Rate (%)", min_value=50, max_value=100, value=95, step=1, help="The target percentage of total calls that should be answered (not abandoned).")
    shrinkage = st.slider("Shrinkage (%)", min_value=0, max_value=100, value=20, step=1, help="Percentage of paid time that agents are not available to handle calls (meetings, breaks, etc.).")





if st.button("Calculate Required FTE", type="primary", use_container_width=True):
    # --- Calculations ---
    avg_calls_per_hour = calls_per_day / hours_of_operation
    avg_patience_sec = 150

    # 1. Calculate FTE for Inbound Calls
    inbound_fte_on_floor = erlang_a_fte(
        calls_per_hour=avg_calls_per_hour,
        aht_sec=aht_sec,
        target_sla=(target_sla / 100),
        sla_threshold_sec=sla_threshold_sec,
        target_answer_rate=(target_answer_rate / 100),
        avg_patience_sec=avg_patience_sec,
        shrinkage=0 # Shrinkage is applied to the final rostered FTE
    )
    
    if inbound_fte_on_floor:
        # Adjust for shrinkage and shift coverage to get total rostered FTE
        total_inbound_fte = inbound_fte_on_floor * coverage_factor / (1 - (shrinkage/100))

        # 2. Calculate FTE for Outbound Tasks
        total_ob_seconds = outbound_referrals_per_day * avg_time_per_referral_sec
        agent_productive_seconds_per_day = agent_work_hours * 3600 * (1 - (shrinkage/100))
        outbound_fte = total_ob_seconds / agent_productive_seconds_per_day if agent_productive_seconds_per_day > 0 else 0

        # --- Display Results ---
        st.success(f"### Total FTE Required: {total_inbound_fte + outbound_fte:.1f}")
        
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.metric(label="Inbound FTE Required", value=f"{total_inbound_fte:.1f}")
        with res_col2:
            st.metric(label="Outbound FTE Required", value=f"{outbound_fte:.1f}")

    else:
        st.error("Could not compute FTE with the given parameters. Try increasing Average Patience or lowering targets.")