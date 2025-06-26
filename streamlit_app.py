import streamlit as st
import math

# --- Erlang A Approximation Function ---
def erlang_a_fte(calls_per_hour, aht_sec, target_sla=0.8, sla_threshold_sec=30,
                 abandonment_rate_per_min=2.0, max_agents=100, shrinkage=0.3):
    lambda_per_sec = calls_per_hour / 3600
    mu = 1 / aht_sec
    theta = abandonment_rate_per_min / 60  # convert to per second
  
    for n in range(1, max_agents):
        rho = lambda_per_sec / (n * mu)
        if rho >= 1:
            continue

        prob = []
        for k in range(n):
            prob.append((lambda_per_sec / mu)**k / math.factorial(k))
        prob.append((lambda_per_sec / mu)**n / (math.factorial(n) * (1 - rho)))
        p0 = 1 / sum(prob)

        pn = prob[-1] * p0
        pa = (n * mu) / (n * mu + theta)
        pw = pn * pa

        if pw <= (1 - target_sla):
            return math.ceil(n / (1 - shrinkage))

    return None

hours_of_operation = 9       # open 9 hours
agent_work_hours = 8         # but agents work only 8 hours
coverage_ratio = agent_work_hours / hours_of_operation  # 8/9
abandonment_rate = 2

def round_to_1_sig_fig(x):
    if x == 0:
        return 0
    return round(x, -int(math.floor(math.log10(abs(x)))))

# --- Streamlit App UI ---
st.title("ECC Staffing Simulator")

calls_per_hour = st.number_input("Calls per Day", min_value=1, value=250)
aht_sec = st.number_input("Average Handle Time (seconds)", min_value=1, value=360)
target_sla = st.slider("Target Service Level (%)", min_value=50, max_value=100, value=80, step=5)
sla_threshold_sec = st.number_input("Service Level Threshold (seconds)", value=30)
shrinkage = st.slider("Shrinkage (%)", min_value=0, max_value=100, value=30, step=5)
outbound_referrals_per_day = st.number_input("Referrals per Day", min_value=1, value=60)
avg_time_per_referral_sec = st.number_input("Average Referral Processing Time (seconds)", min_value=1, value=360)

if st.button("Calculate Required FTE"):
    fte_required = erlang_a_fte(calls_per_hour/hours_of_operation, aht_sec, target_sla/100, sla_threshold_sec,
                                 abandonment_rate, shrinkage=shrinkage/100)/coverage_ratio
   
    ob_fte = (outbound_referrals_per_day * avg_time_per_referral_sec)/((agent_work_hours*3600)*(1 - (shrinkage/100)))
    
    if fte_required:
        st.success(f"Inbound FTE Required: {fte_required:.1f}")
        st.success(f"Outbound FTE Required: {ob_fte:.1f}")
        st.success(f"Total FTE Required: {fte_required+ob_fte:.1f}")
    else:
        st.error("Could not compute FTE with given parameters.")