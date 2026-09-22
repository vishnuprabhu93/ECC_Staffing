# ECC Staffing Simulator

Streamlit app that estimates the daily FTE needed for an ECC pod. It compares two ways of organizing the team:

1. **Dedicated teams**: separate inbound (phones) and outbound (tasks/referrals) staff.
2. **Blended team**: every agent takes calls first and works outbound tasks between calls.

## Method

* **Inbound** uses the exact **Erlang A** model (M/M/n+M), which accounts for callers hanging up. It returns service level, answer rate, occupancy and average wait for each headcount. The required headcount is the smallest that meets the service level, answer rate and maximum occupancy goals. Volume is assumed flat across the operating day.
* **FTE** = agents on floor × (hours open ÷ shift hours) ÷ (1 − shrinkage).
* **Dedicated outbound FTE** = outbound work hours ÷ (shift hours × (1 − shrinkage) × max occupancy).
* **Blended team** is sized by simulating 300 operating days. Calls always have priority. An agent starts an outbound task only when no call is waiting and more than a set number of agents (the reserve: 0, 1 or 2) would stay idle. Outbound tasks are not interrupted once started. The app picks the smallest team and reserve that meets every goal, including same-day outbound completion.

## Files

| File | Purpose |
|---|---|
| `streamlit_app.py` | User interface |
| `erlang.py` | Exact Erlang A engine (plus Erlang C for comparison) |
| `simulate.py` | Day-level simulation of a blended team |
| `staffing.py` | Dedicated and blended staffing plans |
| `test_erlang.py` | Checks Erlang A against simulation and against Erlang C in the infinite-patience limit |

## Run locally

```
pip install -r requirements.txt
streamlit run streamlit_app.py
python test_erlang.py
```

## Estimating caller patience

Average patience = total waiting time of **all** calls (answered and abandoned) ÷ number of abandoned calls. Pull both from the phone system for the same period.
