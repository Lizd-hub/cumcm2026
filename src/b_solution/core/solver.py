"""Online simulated robot policy. It receives protocol results, never source truth."""
from dataclasses import dataclass, field
import math
import numpy as np
from .geometry import (DELTA_DEG, unit, outer_disk, observe, minimum_circle,
                       clip_all, safe_second_point)


def coverage_sites(mixed=False, lattice_step=950.):
    if not mixed:
        return np.array([[0., 0.]] + [(900 * math.sqrt(3) * unit(k * 60)).tolist() for k in range(6)])
    # Every point in a triangular lattice cell is at most one edge length
    # from ALL three vertices. Include the external ring for boundary sources.
    a = lattice_step
    if not 0 < a <= 1000:
        raise ValueError('A coverage proof requires 0 < lattice_step <= 1000.')
    n = math.ceil((1800 + a) / (a * math.sqrt(3) / 2)) + 2
    pts = []
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            p = a * np.array([i + j / 2, math.sqrt(3) * j / 2])
            if np.linalg.norm(p) <= 1800 + a + 1e-8:
                pts.append(p)
    pts.sort(key=lambda p: (float(np.linalg.norm(p)), math.atan2(p[1], p[0])))
    return np.array(pts)


@dataclass
class Target:
    channel: int
    poly: np.ndarray = field(default_factory=lambda: outer_disk([0, 0], 1800.))
    observations: list = field(default_factory=list)
    tried: list = field(default_factory=list)
    cleared: bool = False

    def assimilate(self, position, result):
        if result['measure_result'] == 'direction':
            theta = result['svd_deg']
            new_poly = observe(self.poly, position, theta)
            if len(new_poly) == 0:
                # Do not discard contradictory readings or enlarge the stated
                # physical error automatically. A protocol/model issue needs review.
                raise RuntimeError(f'Empty feasible set on channel {self.channel}')
            self.poly = new_poly
            self.observations.append((np.asarray(position).copy(), theta))


class Solver:
    def __init__(self, session, mixed=False, improved=True, lattice_step=950.):
        self.session = session
        self.mixed = mixed
        self.improved = improved
        self.sites = coverage_sites(mixed, lattice_step)
        self.targets = {}
        self.cleared = set()
        self.visited = []
        self.fallbacks = 0
        self.completion_reason = 'not_started'

    def clear_at(self, target, point):
        result = self.session.action('/clear', point, target.channel)
        if result['clear_result'] == 'success':
            target.cleared = True
            self.cleared.add(target.channel)
            return True
        return False

    def measure(self, target, point):
        target.tried.append(np.asarray(point).copy())
        result = self.session.action('/measure', point, target.channel)
        if result['measure_result'] == 'near':
            if not self.clear_at(target, point):
                raise RuntimeError('near followed by failed clear: simulator/model inconsistency.')
        else:
            target.assimilate(point, result)
        return result

    def next_point(self, target, attempt):
        c, r = minimum_circle(target.poly)
        s, theta = target.observations[0]
        v = unit(theta + 90)
        if not self.improved:
            if attempt == 0:
                return c + min(150., r * .25) * v
            # Distinct viewpoints; no same-place averaging.
            return c + min(80., max(25., r * .35)) * unit(theta + attempt * 137.5)
        scale = min(180., max(30., .30 * r))
        candidates = [c] + [c + scale * unit(theta + k * 45) for k in range(8)]
        candidates = [q for q in candidates if not any(np.linalg.norm(q - old) < 2 for old in target.tried)]
        if not self.mixed and len(target.observations) == 1:
            safe = [q for q in candidates if safe_second_point(q, s, theta)]
            if safe:
                candidates = safe
        if not candidates:
            return c + scale * unit(theta + attempt * 137.5)
        # Finite scenario lookahead: score remaining geometric uncertainty and
        # travel. Its scenario sampling is a heuristic, NOT a worst-case proof.
        samples = np.vstack([target.poly, c])
        if len(samples) > 7:
            samples = samples[np.linspace(0, len(samples) - 1, 7).astype(int)]
        def score(q):
            worst = 0.
            for g in samples:
                if np.linalg.norm(g - q) <= 5:
                    worst = max(worst, 5.)
                    continue
                bearing = math.degrees(math.atan2(g[1] - q[1], g[0] - q[0]))
                # The no-signal branch for unknown directional axes is handled
                # by alternative views and the finite optical-cover fallback.
                p = observe(target.poly, q, bearing)
                _, rr = minimum_circle(p)
                worst = max(worst, rr)
            return np.linalg.norm(q - self.session.position) / 5 + 5 + 2 * worst / 5
        return min(candidates, key=score)

    def optical_cover(self, target):
        """Finite 25 m grid in the first-bearing frame, independent of emission.

        For default error the entire 1500 m wedge is covered by <=180 squares;
        cell centres are <=25/sqrt(2)<20 m from any point in their cells.
        Filter against the current conservative polygon, never against samples.
        """
        self.fallbacks += 1
        s, theta = target.observations[0]
        u, v = unit(theta), unit(theta + 90)
        basis = np.array([u, v])
        poly = (target.poly - s) @ basis.T
        halfwidth = 1500 * math.sin(math.radians(DELTA_DEG))
        max_j = math.ceil(halfwidth / 25 - .5)
        cells = []
        for i in range(60):
            for j in range(-max_j, max_j + 1):
                x, y = (i + .5) * 25, j * 25
                a = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]])
                b = np.array([x + 12.5, -x + 12.5, y + 12.5, -y + 12.5])
                if len(clip_all(poly, a, b)):
                    cells.append((i, j, s + x * u + y * v))
        # Compare the full greedy route with four serpentine routes. The latter
        # bound the default strip's internal travel by 4475 m. Taking the shorter
        # route preserves this bound without discarding any candidate cell.
        routes = []
        remaining = [p for _, _, p in cells]
        greedy, current = [], self.session.position.copy()
        while remaining:
            k = min(range(len(remaining)), key=lambda k: np.linalg.norm(remaining[k] - current))
            current = remaining.pop(k)
            greedy.append(current)
        routes.append(greedy)
        for reverse_rows in (False, True):
            js = list(range(-max_j, max_j + 1))
            if reverse_rows:
                js.reverse()
            for reverse_first in (False, True):
                route = []
                for row_index, j in enumerate(js):
                    row = sorted([(i, p) for i, jj, p in cells if jj == j],
                                 key=lambda z: z[0], reverse=reverse_first ^ bool(row_index % 2))
                    route.extend(p for _, p in row)
                routes.append(route)
        def route_length(route):
            if not route:
                return 0.
            points = np.vstack([self.session.position, route])
            return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
        route = min(routes, key=route_length)
        for point in route:
            if self.clear_at(target, point):
                return
        raise RuntimeError('Exhausted a certified cover without success: stop and inspect logs.')

    def localize(self, target):
        opportunistic = False
        for attempt in range(6):
            if target.cleared:
                return
            c, r = minimum_circle(target.poly)
            if r <= 19.75:
                if not self.clear_at(target, c):
                    raise RuntimeError('Certified clear failed: geometry/protocol inconsistency.')
                return
            # A failed optical attempt costs only 3 s. This optional action is
            # explicitly speculative, not mistaken for a certified 20 m clear.
            if self.improved and r <= 40 and not opportunistic:
                opportunistic = True
                if self.clear_at(target, c):
                    return
            self.measure(target, self.next_point(target, attempt))
        if not target.cleared:
            self.optical_cover(target)

    def run(self):
        self.session.enter()
        remaining = list(range(len(self.sites)))
        while remaining:
            if len(self.cleared) == 16:
                self.completion_reason = 'known_upper_bound_16'
                break
            if self.improved:
                index = min(remaining, key=lambda k: np.linalg.norm(self.sites[k] - self.session.position))
            else:
                index = remaining[0]
            remaining.remove(index)
            q = self.sites[index]
            channels = [c for c in range(1, 21) if c not in self.cleared]
            # Same-site batch: save a switch by measuring the current channel first.
            if self.improved and self.session.channel in channels:
                channels.remove(self.session.channel)
                channels.insert(0, self.session.channel)
            pending = []
            for ch in channels:
                t = self.targets.setdefault(ch, Target(ch))
                r = self.measure(t, q)
                if r['measure_result'] == 'direction':
                    pending.append(t)
            self.visited.append(index)
            while pending:
                if self.improved:
                    target = min(pending, key=lambda t: np.linalg.norm(minimum_circle(t.poly)[0] - self.session.position))
                    pending.remove(target)
                else:
                    target = pending.pop(0)
                self.localize(target)
        else:
            self.completion_reason = 'all_uncleared_channels_scanned_at_complete_cover'
        self.session.exit()
        return {'cleared': len(self.cleared), 'virtual_time_s': self.session.virtual_time,
                'average_time_s': self.session.virtual_time / len(self.cleared) if self.cleared else None,
                'sites_visited': len(self.visited), 'sites_planned': len(self.sites),
                'fallbacks': self.fallbacks, 'completion_reason': self.completion_reason,
                **self.session.stats}
