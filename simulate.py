"""
Discrete-event simulation of one operating day for a BLENDED team.

Policy (standard call-blending rule):
  * Inbound calls always have priority over outbound work.
  * An agent who becomes free takes the next waiting call if there is one.
  * Otherwise the agent starts an outbound task only if more than `reserve`
    agents would be left idle for inbound (reserve = agents held back for calls).
  * Outbound tasks are not interrupted once started.
Inbound: Poisson arrivals, exponential handle time and patience (Erlang A world).
Outbound tasks arrive evenly through the day; unfinished tasks carry over.
"""
from __future__ import annotations

import collections
import heapq
from dataclasses import dataclass

import numpy as np

ARRIVAL, CALL_DONE, OB_ARRIVAL, OB_DONE = 0, 1, 2, 3


@dataclass
class DayResult:
    service_level: float
    answer_rate: float
    outbound_done: float     # share of the day's outbound tasks completed
    occupancy: float


def simulate_day(agents, calls_per_day, aht_sec, patience_sec, sl_threshold_sec,
                 ob_tasks_per_day, ob_aht_sec, hours_open, reserve=1, rng=None) -> DayResult:
    rng = rng or np.random.default_rng()
    T = hours_open * 3600.0
    n_calls = rng.poisson(calls_per_day)
    n_ob = int(round(ob_tasks_per_day))
    ev = [(t, ARRIVAL) for t in np.sort(rng.uniform(0, T, n_calls))]
    ev += [(t, OB_ARRIVAL) for t in np.sort(rng.uniform(0, T, n_ob))]
    heapq.heapify(ev)

    idle = agents
    queue = collections.deque()          # (arrival_time, abandon_time)
    backlog = 0
    answered_in_t = abandoned = ob_done = 0
    busy_time = 0.0

    def start_call(now, arr_time):
        nonlocal busy_time, answered_in_t
        d = rng.exponential(aht_sec)
        busy_time += min(d, max(T - now, 0))
        answered_in_t += (now - arr_time) <= sl_threshold_sec
        heapq.heappush(ev, (now + d, CALL_DONE))

    def start_ob(now):
        nonlocal busy_time, backlog
        backlog -= 1
        d = rng.exponential(ob_aht_sec)
        busy_time += min(d, max(T - now, 0))
        heapq.heappush(ev, (now + d, OB_DONE))

    def next_waiting_call(now):
        nonlocal abandoned
        while queue and queue[0][1] < now:
            queue.popleft(); abandoned += 1
        return queue.popleft() if queue else None

    while ev:
        now, kind = heapq.heappop(ev)
        if kind == ARRIVAL:
            if idle > 0:
                idle -= 1; start_call(now, now)
            else:
                queue.append((now, now + rng.exponential(patience_sec)))
        elif kind == OB_ARRIVAL:
            backlog += 1
            if idle > reserve and now < T:
                idle -= 1; start_ob(now)
        else:  # an agent just finished something
            if kind == OB_DONE:
                ob_done += 1
            call = next_waiting_call(now)
            if call is not None:
                start_call(now, call[0])
            elif backlog > 0 and idle + 1 > reserve and now < T:
                start_ob(now)
            else:
                idle += 1
    # anyone still in queue at end of day with patience expired counts as abandoned
    abandoned += len(queue)
    n = max(n_calls, 1)
    return DayResult(answered_in_t / n, 1 - abandoned / n,
                     ob_done / n_ob if n_ob else 1.0, busy_time / (agents * T))


def simulate(agents, calls_per_day, aht_sec, patience_sec, sl_threshold_sec,
             ob_tasks_per_day, ob_aht_sec, hours_open, reserve=1, days=300, seed=7) -> dict:
    rng = np.random.default_rng(seed)
    res = [simulate_day(agents, calls_per_day, aht_sec, patience_sec, sl_threshold_sec,
                        ob_tasks_per_day, ob_aht_sec, hours_open, reserve, rng) for _ in range(days)]
    arr = lambda f: np.array([getattr(r, f) for r in res])
    sl, ar, ob, occ = arr("service_level"), arr("answer_rate"), arr("outbound_done"), arr("occupancy")
    return {"agents": agents, "reserve": reserve,
            "service_level": sl.mean(), "answer_rate": ar.mean(),
            "outbound_done": ob.mean(), "occupancy": occ.mean(),
            "pct_days_sl_met": None, "sl_p10": np.percentile(sl, 10)}
