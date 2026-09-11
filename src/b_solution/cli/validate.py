"""Meaningful geometry, protocol-state and coverage checks."""
import math
import numpy as np
from ..core.geometry import (wedge_halfplanes, halfplane_polygon, convex_hull, diameter_brute,
                       diameter_calipers, minimum_circle, safe_second_point, unit)
from ..core.solver import coverage_sites
from ..infrastructure.offline_simulator import OfflineSimulator
from ..infrastructure.protocol import Session


def validate():
    checks = []
    p = np.array([[0, 0], [40, 0], [20, 20 * math.sqrt(3)]])
    d, _ = diameter_calipers(p)
    c, r = minimum_circle(p)
    assert abs(d - 40) < 1e-9 and abs(r - 40 / math.sqrt(3)) < 1e-9
    checks.append('Equilateral triangle: diameter 40 m but enclosing radius 23.094 m')
    rng = np.random.default_rng(87)
    for _ in range(100):
        h = convex_hull(rng.normal(size=(30, 2)))
        assert abs(diameter_brute(h)[0] - diameter_calipers(h)[0]) < 1e-8
    checks.append('Rotating calipers equals exhaustive diameter on 100 random convex hulls')
    a, b = wedge_halfplanes([0, 0], 359.8)
    assert halfplane_polygon(a, b)[0] == 'unbounded'
    assert np.all(a @ unit(.2) <= b + 1e-10)
    assert not np.all(a @ (-unit(.2)) <= b + 1e-10)
    a = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]])
    assert halfplane_polygon(a, np.array([0, -1, 1, 1]))[0] == 'empty'
    status, segment = halfplane_polygon(a, np.array([0, 0, 1, 0]))
    assert status == 'bounded' and abs(diameter_brute(segment)[0] - 1) < 1e-8
    checks.append('Angle wrap, forward wedge, empty intersection, unbounded intersection and line segment')
    for _ in range(2000):
        q = rng.uniform([-50, -1000], [1000, 1000])
        if safe_second_point(q, [0, 0], 0):
            d = rng.uniform(0, 1500)
            g = d * unit(rng.uniform(-1.005, 1.005))
            assert np.linalg.norm(q - g) <= max(1000, d) + 1e-7
    checks.append('Omnidirectional second-point reception lens: randomized necessary geometry checks')
    points = []
    for radius in np.linspace(0, 1800, 91):
        for angle in np.linspace(0, 360, 181)[:-1]:
            points.append(radius * unit(angle))
    points = np.array(points)
    omni = coverage_sites(False)
    max_dist = np.linalg.norm(points[:, None] - omni[None, :], axis=2).min(axis=1).max()
    assert max_dist <= 900 + 1e-7
    mixed = coverage_sites(True)
    # This grid test supplements, and does not replace, the convex-hull proof.
    for g in points[::11]:
        d = mixed - g
        close = d[np.linalg.norm(d, axis=1) <= 1000 + 1e-8]
        for a in np.linspace(0, 360, 72, endpoint=False):
            assert np.any(close @ unit(a) >= -1e-8)
    checks.append(f'Coverage samples: 7 omni sites, {len(mixed)} mixed sites; all headings tested')
    sim = OfflineSimulator(8)
    sim._sources = {}  # Test fixture, used only here; solver never accesses truth.
    s = Session(sim)
    s.enter()
    s.action('/measure', [300, 400], 1)
    assert abs(s.virtual_time - 105) < 1e-9
    s.action('/measure', [300, 400], 2)
    assert abs(s.virtual_time - 111) < 1e-9
    s.action('/clear', [300, 0], 3)
    assert abs(s.virtual_time - 194) < 1e-9 and s.channel == 2
    s.action('/measure', [300, 0], 2)
    assert abs(s.virtual_time - 199) < 1e-9
    payload = s.records[-1]['request']
    old = sim.vt
    r1, r2 = sim.request('/measure', payload), sim.request('/measure', payload)
    assert r1 == r2 and sim.vt == old
    s.exit()
    checks.append('Attachment example 105→111→194→199 s; clear preserves channel; retry is idempotent')
    return checks


def main():
    """Run all deterministic validation checks and print their outcomes."""
    for item in validate():
        print('PASS:', item)


if __name__ == '__main__':
    main()
