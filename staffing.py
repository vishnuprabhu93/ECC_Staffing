"""
Daily staffing calculations: dedicated inbound + dedicated outbound vs a blended team.
Call volume is assumed flat across the operating day (daily-level planning).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from erlang import QueueMetrics, erlang_a, erlang_c, required_agents
from simulate import simulate


@dataclass
class Inputs:
    calls_per_day: float
    aht_sec: float
    ob_tasks_per_day: float
    ob_aht_sec: float
    hours_open: float
    shift_hours: float
    target_sl: float            # 0-1
    sl_threshold_sec: float
    target_answer_rate: float   # 0-1
    patience_sec: float
    shrinkage: float            # 0-1
    max_occupancy: float        # 0-1
    ob_completion_target: float = 0.98

    @property
    def calls_per_hour(self) -> float:
        return self.calls_per_day / self.hours_open

    @property
    def ob_work_hours(self) -> float:
        return self.ob_tasks_per_day * self.ob_aht_sec / 3600.0

    def rostered_fte(self, floor_agents: float) -> float:
        """On-floor seats across the open day -> paid FTE (shift coverage + shrinkage)."""
        return floor_agents * (self.hours_open / self.shift_hours) / (1 - self.shrinkage)


@dataclass
class DedicatedPlan:
    inbound: QueueMetrics | None
    inbound_fte: float
    outbound_fte: float

    @property
    def total_fte(self) -> float:
        return self.inbound_fte + self.outbound_fte


@dataclass
class BlendedPlan:
    agents: int | None
    reserve: int | None
    fte: float | None
    sim: dict | None
    tried: list = field(default_factory=list)


def dedicated_plan(x: Inputs) -> DedicatedPlan:
    m = required_agents(x.calls_per_hour, x.aht_sec, x.patience_sec, x.target_sl,
                        x.sl_threshold_sec, x.target_answer_rate, x.max_occupancy)
    inbound_fte = x.rostered_fte(m.agents) if m else float("nan")
    productive_hours_per_fte = x.shift_hours * (1 - x.shrinkage) * x.max_occupancy
    outbound_fte = x.ob_work_hours / productive_hours_per_fte if productive_hours_per_fte else 0.0
    return DedicatedPlan(m, inbound_fte, outbound_fte)


def blended_plan(x: Inputs, start_agents: int, days: int = 300, max_extra: int = 15,
                 reserves=(0, 1, 2)) -> BlendedPlan:
    """
    Smallest blended team (and reserve setting) that, in simulation, meets the
    inbound service level, answer rate, outbound completion target and occupancy cap.
    Search starts at the dedicated-inbound headcount, since blending can never need fewer.
    """
    tried = []
    for n in range(start_agents, start_agents + max_extra + 1):
        for r in reserves:
            if r >= n:
                continue
            s = simulate(n, x.calls_per_day, x.aht_sec, x.patience_sec, x.sl_threshold_sec,
                         x.ob_tasks_per_day, x.ob_aht_sec, x.hours_open, reserve=r, days=days)
            tried.append(s)
            if (s["service_level"] >= x.target_sl and s["answer_rate"] >= x.target_answer_rate
                    and s["outbound_done"] >= x.ob_completion_target
                    and s["occupancy"] <= x.max_occupancy):
                return BlendedPlan(n, r, x.rostered_fte(n), s, tried)
    return BlendedPlan(None, None, None, None, tried)


def inbound_curve(x: Inputs, n_from: int, n_to: int) -> list[dict]:
    rows = []
    for n in range(max(1, n_from), n_to + 1):
        a = erlang_a(n, x.calls_per_hour, x.aht_sec, x.patience_sec, x.sl_threshold_sec)
        c = erlang_c(n, x.calls_per_hour, x.aht_sec, x.sl_threshold_sec)
        rows.append({
            "Agents on floor": n,
            "Service level (Erlang A)": a.service_level,
            "Answer rate (Erlang A)": a.answer_rate,
            "Service level (Erlang C)": c["service_level"] if c else None,
            "Occupancy": a.occupancy,
            "Avg wait (s)": a.avg_wait_sec,
            "Rostered FTE": x.rostered_fte(n),
        })
    return rows


def erlang_c_agents(x: Inputs) -> int | None:
    """What classic Erlang C would ask for (service level only; it cannot model answer rate)."""
    a = x.calls_per_hour * x.aht_sec / 3600
    for n in range(max(1, math.floor(a) + 1), 1000):
        c = erlang_c(n, x.calls_per_hour, x.aht_sec, x.sl_threshold_sec)
        if c and c["service_level"] >= x.target_sl and c["occupancy"] <= x.max_occupancy:
            return n
    return None
