import numpy as np
import pytest

from b_solution.core.geometry import minimum_circle, minimum_circle_reference, convex_hull, observe, outer_disk
from b_solution.core.planning import optical_pieces, excluded, order_points, route_length, reception_probability
from b_solution.core.solver import Solver, Target
from b_solution.infrastructure.protocol import Session
from b_solution.infrastructure.offline_simulator import OfflineSimulator


def test_incremental_circle_matches_exhaustive_reference():
    rng = np.random.default_rng(183)
    cases = [np.array([[0., 0.]]), np.array([[0., 0.], [10., 0.], [5., 0.]]),
             np.array([[0., 0.], [40., 0.], [20., 20 * np.sqrt(3)]])]
    cases += [convex_hull(rng.normal(size=(20, 2)) * [1000, scale])
              for scale in (1e-8, .1, 1000) for _ in range(30)]
    for p in cases:
        c, r = minimum_circle(p)
        _, reference = minimum_circle_reference(p)
        assert r == pytest.approx(reference, rel=1e-7, abs=1e-6)
        assert np.max(np.linalg.norm(p - c, axis=1)) <= r + 1e-9


def test_optical_partition_covers_wedge_and_interior():
    poly = observe(outer_disk([0, 0], 1800), [0, 0], 17)
    pieces = optical_pieces(poly)
    assert len(pieces) < 180
    rng = np.random.default_rng(12)
    samples = np.vstack([poly, rng.dirichlet(np.ones(len(poly)), size=2000) @ poly])
    centers = np.array([c for c, _ in pieces])
    assert np.max(np.min(np.linalg.norm(samples[:, None] - centers, axis=2), axis=1)) <= 19.5 + 1e-7
    for c, piece in pieces:
        assert np.max(np.linalg.norm(piece - c, axis=1)) <= 19.5 + 1e-7


def test_exclusions_require_entire_piece_not_just_center():
    piece = np.array([[-25., 0], [25., 0], [0, 2]])
    assert not excluded(piece, [(np.zeros(2), 20)])
    assert excluded(piece / 2, [(np.zeros(2), 20)])
    assert not excluded(np.array([[20., 0]]), [(np.zeros(2), 20)])


def test_circle_cache_invalidates_with_observation():
    t = Target(1)
    initial = t.circle()
    assert t.circle() is initial
    t.assimilate([0, 0], {'measure_result': 'direction', 'svd_deg': 0})
    assert t.circle() is not initial
    assert t.circle()[1] < initial[1]


def test_clipping_preserves_true_source_under_extreme_rounded_bearings():
    rng = np.random.default_rng(2026)
    for _ in range(100):
        source = rng.uniform(-500, 500, size=2)
        poly = outer_disk([0, 0], 1800)
        for error in (-1., 1., 0.):
            angle = rng.uniform(0, 2 * np.pi)
            station = source + rng.uniform(10, 1500) * np.array([np.cos(angle), np.sin(angle)])
            bearing = np.degrees(np.arctan2(*(source - station)[::-1]))
            poly = observe(poly, station, round((bearing + error) % 360, 2) % 360)
            assert len(poly)
            edge = np.roll(poly, -1, axis=0) - poly
            offsets = source - poly
            crosses = edge[:, 0] * offsets[:, 1] - edge[:, 1] * offsets[:, 0]
            assert np.min(crosses) >= -1e-6


def test_directional_negative_keeps_nearby_source_hypothesis():
    t = Target(1, observations=[(np.array([100., 0]), 180.)], negative=[np.array([-100., 0])])
    assert reception_probability(t, np.zeros(2), np.array([100., 0]), True) == 1
    assert reception_probability(t, np.zeros(2), np.array([-100., 0]), True) == 0


def test_routes_retain_every_point_and_do_not_exceed_greedy():
    points = np.random.default_rng(7).normal(size=(20, 2))
    start = np.zeros(2)
    order = order_points(start, points)
    assert sorted(order) == list(range(len(points)))
    remaining, greedy, current = list(range(len(points))), [], start
    while remaining:
        k = min(remaining, key=lambda i: np.linalg.norm(points[i] - current))
        remaining.remove(k)
        greedy.append(k)
        current = points[k]
    assert route_length(start, points[order]) <= route_length(start, points[greedy]) + 1e-8


@pytest.mark.parametrize('mixed', [False, True])
@pytest.mark.parametrize('stress', [False, True])
def test_optimized_policy_completes_without_truth_access(mixed, stress):
    sim = OfflineSimulator(31, mixed, 'min' if stress else 'random', 'extreme' if stress else 'smooth', stress)
    class ProtocolOnly:
        def request(self, path, payload):
            return sim.request(path, payload)
    session = Session(ProtocolOnly())
    solver = Solver(session, mixed)
    result = solver.run()
    assert result['cleared'] == sim.evaluate()['total']
    assert sim.evaluate()['clear_fraction'] == 1
    reconstructed = result['distance_m'] / 5 + 5 * result['measurements'] + result['switches'] + 5 * result['clear_success'] + 3 * result['clear_failed']
    assert reconstructed == pytest.approx(result['virtual_time_s'], abs=.002)
    if mixed:
        assert all(radius == 20 for t in solver.targets.values() for _, radius in t.exclusions)


def test_benchmark_records_failure_and_exits(monkeypatch):
    from b_solution.cli.benchmark import run_case, summarize_group
    def fail(solver):
        solver.session.enter()
        raise TimeoutError('injected deadline')
    monkeypatch.setattr(Solver, 'run', fail)
    row, sim, session, _ = run_case(0, 4)
    assert not row['completed'] and 'injected deadline' in row['failure_reason']
    assert not session.started and not sim.active
    summary = summarize_group([row])
    assert summary['complete_success_rate'] == 0
    assert summary['mean_case_average_s'] is None
    assert len(summary['failures']) == 1


def test_transport_retries_lost_response_with_identical_action(monkeypatch):
    import http.client
    import json
    from b_solution.infrastructure.protocol import HTTPTransport
    sim = OfflineSimulator(0)
    requests = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps(self.response).encode()
    def urlopen(request, timeout):
        requests.append(request.data)
        response = sim.request('/enter', json.loads(request.data))
        if len(requests) == 1:
            raise http.client.RemoteDisconnected('response lost after accepted action')
        result = Response()
        result.response = response
        return result
    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    session = Session(HTTPTransport())
    session.enter()
    assert session.started
    assert requests[0] == requests[1]
    assert len(sim.cache) == 1


def test_deadline_and_next_action_virtual_cost_checked_before_send():
    import time
    sim = OfflineSimulator(0)
    s = Session(sim)
    s.enter()
    s.max_virtual_duration = 100
    with pytest.raises(TimeoutError, match='virtual-time'):
        s.action('/measure', [500, 0], 1)
    assert sim.vt == 0
    s.deadline = time.monotonic() + 1
    with pytest.raises(TimeoutError, match='Safety deadline'):
        s.action('/measure', [0, 0], 1)
    s.exit()
    assert not s.started
