"""
Exact Erlang A (M/M/n+M, Palm's model) queueing engine.

Assumptions (same as all Erlang models): Poisson arrivals, exponential handle
time, and exponential caller patience. Unlike Erlang C, callers who wait longer
than their patience hang up, so the queue is always stable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm


@dataclass
class QueueMetrics:
    agents: int
    offered_erlangs: float
    prob_wait: float          # share of callers who have to wait at all
    service_level: float      # answered within threshold / all offered calls
    abandon_rate: float       # share of offered calls that hang up
    answer_rate: float        # 1 - abandon_rate
    avg_wait_sec: float       # mean wait across all callers (answered + abandoned)
    occupancy: float          # share of on-floor agent time spent on calls


def _stationary(n: int, lam: float, mu: float, theta: float, max_queue: int) -> np.ndarray:
    """Birth-death stationary distribution for states 0..n+max_queue (log space for stability)."""
    K = n + max_queue
    logp = np.zeros(K + 1)
    for k in range(1, K + 1):
        death = min(k, n) * mu + max(k - n, 0) * theta
        logp[k] = logp[k - 1] + math.log(lam / death)
    p = np.exp(logp - logp.max())
    return p / p.sum()


def _prob_served_within(n: int, mu: float, theta: float, t: float, J: int) -> np.ndarray:
    """
    For an arriving caller who finds j callers already waiting (j = 0..J), the
    probability they reach an agent within t seconds without abandoning.
    Absorbing Markov chain: state = callers ahead; ahead-queue shrinks at rate
    n*mu + i*theta; the caller abandons at rate theta.
    """
    size = J + 3
    served, abandoned = J + 1, J + 2
    Q = np.zeros((size, size))
    for i in range(J + 1):
        Q[i, i] = -(n * mu + i * theta + theta)
        if i > 0:
            Q[i, i - 1] = n * mu + i * theta
        else:
            Q[i, served] = n * mu
        Q[i, abandoned] = theta
    return expm(Q * t)[: J + 1, served]


def erlang_a(n: int, calls_per_hour: float, aht_sec: float, patience_sec: float,
             sl_threshold_sec: float, max_queue: int | None = None) -> QueueMetrics:
    lam = calls_per_hour / 3600.0
    mu = 1.0 / aht_sec
    theta = 1.0 / patience_sec
    a = lam / mu
    if max_queue is None:
        # queue long enough that truncation is negligible
        max_queue = int(max(60, 4 * a + 10 * math.sqrt(a + 1)))
    p = _stationary(n, lam, mu, theta, max_queue)
    queue_probs = p[n:]                       # arrival sees n busy + j waiting (PASTA)
    prob_wait = float(queue_probs.sum())
    lq = float(np.dot(np.arange(len(queue_probs)), queue_probs))
    abandon = theta * lq / lam
    served_t = _prob_served_within(n, mu, theta, sl_threshold_sec, len(queue_probs) - 1)
    sl = float(p[:n].sum() + np.dot(queue_probs, served_t))
    return QueueMetrics(
        agents=n,
        offered_erlangs=a,
        prob_wait=prob_wait,
        service_level=sl,
        abandon_rate=abandon,
        answer_rate=1 - abandon,
        avg_wait_sec=lq / lam,
        occupancy=a * (1 - abandon) / n,
    )


def erlang_c(n: int, calls_per_hour: float, aht_sec: float, sl_threshold_sec: float) -> dict | None:
    """Classic Erlang C (no abandonment), for comparison only. Uses the stable Erlang B recursion."""
    lam = calls_per_hour / 3600.0
    mu = 1.0 / aht_sec
    a = lam / mu
    if a >= n:
        return None
    b = 1.0
    for k in range(1, n + 1):
        b = a * b / (k + a * b)
    pw = b / (1 - (a / n) * (1 - b))
    sl = 1 - pw * math.exp(-(n * mu - lam) * sl_threshold_sec)
    return {"agents": n, "prob_wait": pw, "service_level": sl, "occupancy": a / n,
            "avg_wait_sec": pw / (n * mu - lam)}


def required_agents(calls_per_hour: float, aht_sec: float, patience_sec: float,
                    target_sl: float, sl_threshold_sec: float, target_answer_rate: float,
                    max_occupancy: float = 1.0, max_agents: int = 1000) -> QueueMetrics | None:
    """Smallest on-floor headcount meeting service level, answer rate and occupancy cap."""
    if calls_per_hour <= 0:
        return None
    a = calls_per_hour / 3600.0 * aht_sec
    start = max(1, int(math.floor(a * 0.5)))
    for n in range(start, max_agents + 1):
        m = erlang_a(n, calls_per_hour, aht_sec, patience_sec, sl_threshold_sec)
        if (m.service_level >= target_sl and m.answer_rate >= target_answer_rate
                and m.occupancy <= max_occupancy):
            return m
    return None
