import collections, heapq
import numpy as np
from erlang import erlang_a, erlang_c, required_agents

def sim(n, cph, aht, pat, t, hours=3000, seed=1):
    rng = np.random.default_rng(seed); lam = cph/3600; T = hours*3600
    ev = [(rng.exponential(1/lam), 0)]; free = n; q = collections.deque()
    tot = ab = ok = 0
    while ev:
        tm, typ = heapq.heappop(ev)
        if tm > T: break
        if typ == 0:
            tot += 1
            if free: free -= 1; ok += 1; heapq.heappush(ev, (tm+rng.exponential(aht), 1))
            else: q.append((tm, tm+rng.exponential(pat)))
            heapq.heappush(ev, (tm+rng.exponential(1/lam), 0))
        else:
            while q and q[0][1] < tm: q.popleft(); ab += 1
            if q:
                a0, _ = q.popleft(); ok += (tm-a0 <= t)
                heapq.heappush(ev, (tm+rng.exponential(aht), 1))
            else: free += 1
    return ok/tot, ab/tot

def test_matches_simulation():
    for n, cph, aht, pat in [(6, 250/9, 600, 150), (15, 600/9*1.0, 600, 60), (4, 40, 300, 300)]:
        m = erlang_a(n, cph, aht, pat, 30)
        sl, ab = sim(n, cph, aht, pat, 30)
        assert abs(m.service_level - sl) < 0.015, (n, m.service_level, sl)
        assert abs(m.abandon_rate - ab) < 0.01, (n, m.abandon_rate, ab)

def test_converges_to_erlang_c_when_patient():
    a = erlang_a(8, 250/9, 600, 1e7, 30); c = erlang_c(8, 250/9, 600, 30)
    assert abs(a.service_level - c["service_level"]) < 1e-3
    assert abs(a.prob_wait - c["prob_wait"]) < 1e-3

def test_required_agents_default_case():
    m = required_agents(250/9, 600, 150, 0.80, 30, 0.95)
    assert m.agents == 8

if __name__ == "__main__":
    test_matches_simulation(); test_converges_to_erlang_c_when_patient(); test_required_agents_default_case(); print("all pass")
