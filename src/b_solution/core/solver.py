"""Online simulated robot policy. It receives protocol results, never source truth."""
from dataclasses import dataclass, field
import math
import time
import numpy as np
from .geometry import (DELTA_DEG, unit, outer_disk, observe, minimum_circle,
                       clip_all, safe_second_point)
from .planning import optical_pieces, excluded, order_points, route_length, reception_probabilities


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
    negative: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    no_signal_streak: int = 0
    _circle: object = field(default=None, init=False, repr=False)

    def circle(self):
        if self._circle is None:
            self._circle = minimum_circle(self.poly)
        return self._circle

    def assimilate(self, position, result):
        if result['measure_result'] == 'direction':
            theta = result['svd_deg']
            new_poly = observe(self.poly, position, theta)
            if len(new_poly) == 0:
                # Do not discard contradictory readings or enlarge the stated
                # physical error automatically. A protocol/model issue needs review.
                raise RuntimeError(f'Empty feasible set on channel {self.channel}')
            self.poly = new_poly
            self._circle = None
            self.observations.append((np.asarray(position).copy(), theta))


class Solver:
    def __init__(self, session, mixed=False, improved=True, lattice_step=950., optimized=True):
        self.session = session
        self.mixed = mixed
        self.improved = improved
        self.optimized = improved and optimized
        self.sites = coverage_sites(mixed, lattice_step)
        self.targets = {}
        self.cleared = set()
        self.visited = []
        self.fallbacks = 0
        self.completion_reason = 'not_started'
        self.pending = []

    def clear_at(self, target, point):
        result = self.session.action('/clear', point, target.channel)
        if result['clear_result'] == 'success':
            target.cleared = True
            self.cleared.add(target.channel)
            return True
        target.exclusions.append((np.asarray(point).copy(), 20.))
        return False

    def measure(self, target, point):
        target.tried.append(np.asarray(point).copy())
        result = self.session.action('/measure', point, target.channel)
        if result['measure_result'] == 'no_signal':
            target.negative.append(np.asarray(point).copy())
            target.no_signal_streak += 1
            if not self.mixed:
                target.exclusions.append((np.asarray(point).copy(), 1000.))
        else:
            target.no_signal_streak = 0
        if result['measure_result'] == 'near':
            if not self.clear_at(target, point):
                raise RuntimeError('near followed by failed clear: simulator/model inconsistency.')
        else:
            target.assimilate(point, result)
        return result

    def next_point(self, target, attempt):
        if self.optimized:
            return self.planned_measurement(target, attempt)[0]
        c, r = target.circle()
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

    def planned_measurement(self, target, attempt):
        """Bounded noisy lookahead, including an estimated no-signal branch."""
        c, r = target.circle()
        s, theta = target.observations[-1]
        scale = min(180., max(30., .3 * r))
        candidates = [c] + [c + scale * unit(theta + k * 45) for k in range(8)]
        if self.mixed:
            # Approach from the side on which reception has actually occurred.
            approach = s - c
            length = np.linalg.norm(approach)
            if length > 1e-8:
                direction = approach / length
                side = np.array([-direction[1], direction[0]])
                candidates += [c + scale * direction + offset * scale * side for offset in (-.5, 0, .5)]
                # A short baseline beside a proven receiving point can avoid
                # crossing the unknown emission boundary on the way to c.
                if target.no_signal_streak:
                    candidates += [s + offset * side for offset in (-150., -75., 75., 150.)]
                    candidates.append((s + c) / 2)
        candidates = [q for q in candidates if not any(np.linalg.norm(q - p) < 2 for p in target.tried)]
        if not self.mixed and len(target.observations) == 1:
            safe = [q for q in candidates if safe_second_point(q, s, theta)]
            if safe:
                candidates = safe
        if not candidates:
            candidates = [c + scale * unit(theta + attempt * 137.5)]
        p = target.poly
        indices = np.linspace(0, len(p) - 1, min(6, len(p))).astype(int)
        samples = np.vstack([p[indices], p.mean(axis=0)])
        samples = np.array([g for g in samples if not any(np.linalg.norm(g - q) < radius - 1e-6
                            for q, radius in target.exclusions)]).reshape(-1, 2)
        if not len(samples):
            samples = p.mean(axis=0).reshape(1, 2)
        chances = np.array([reception_probabilities(target, g, candidates, self.mixed) for g in samples])
        fallback_cost = 3 * max(1., 2 * r / 35) + 2 * r / 5
        def score(q, index):
            costs = []
            for sample_index, g in enumerate(samples):
                chance = chances[sample_index, index]
                if np.linalg.norm(g - q) <= 5:
                    remaining = 5.
                else:
                    bearing = math.degrees(math.atan2(g[1] - q[1], g[0] - q[0]))
                    radii = []
                    for error in (-1., 0., 1.):
                        region = observe(p, q, round((bearing + error) % 360, 2) % 360)
                        if len(region):
                            radii.append(minimum_circle(region)[1])
                    rr = max(radii, default=r)
                    remaining = 5 + 2 * rr / 5 + (5 if rr > 19.75 else 0)
                costs.append(chance * remaining + (1 - chance) * fallback_cost)
            return (np.linalg.norm(q - self.session.position) / 5 + 5
                    + int(self.session.channel != target.channel)
                    + .7 * float(np.mean(costs)) + .3 * max(costs))
        scores = [score(q, i) for i, q in enumerate(candidates)]
        k = int(np.argmin(scores))
        return candidates[k], scores[k]

    def cover_plan(self, target):
        pieces = optical_pieces(target.poly, target.exclusions)
        order = order_points(self.session.position, [c for c, _ in pieces])
        return [pieces[i] for i in order]

    def share_measurement(self, point):
        """Exploit an existing stop for up to two useful pending channels."""
        choices = []
        for target in self.pending:
            if target.cleared:
                continue
            c, r = target.circle()
            if r <= 19.75 or any(np.linalg.norm(point - p) < 2 for p in target.tried):
                continue
            if np.max(np.linalg.norm(target.poly - point, axis=1)) > 1000:
                continue
            chance = reception_probabilities(target, c, [point], self.mixed)[0]
            if chance < .8:
                continue
            bearing = math.degrees(math.atan2(c[1] - point[1], c[0] - point[0]))
            region = observe(target.poly, point, bearing)
            if not len(region):
                continue
            rr = minimum_circle(region)[1]
            if rr < min(.6 * r, 40.):
                choices.append((r - rr, target))
        for _, target in sorted(choices, key=lambda x: -x[0])[:2]:
            self.measure(target, point)
            # near clears at this same point, so shared stops do not add travel.

    def adaptive_cover(self, target, pieces=None):
        self.fallbacks += 1
        pieces = self.cover_plan(target) if pieces is None else pieces
        for c, poly in pieces:
            if excluded(poly, target.exclusions):
                continue
            if self.clear_at(target, c):
                return
        raise RuntimeError('Exhausted a certified adaptive cover without success.')

    def adaptive_localize(self, target):
        opportunistic = False
        for attempt in range(10):
            if target.cleared:
                return
            c, r = target.circle()
            if r <= 19.75:
                if not self.clear_at(target, c):
                    raise RuntimeError('Certified clear failed: geometry/protocol inconsistency.')
                return
            if (r <= 40 and not opportunistic and np.linalg.norm(c - self.session.position) <= 80
                    and not any(np.linalg.norm(c - p) < 2 for p, _ in target.exclusions)):
                opportunistic = True
                if self.clear_at(target, c):
                    return
            pieces = self.cover_plan(target)
            # Full-route cost is a conservative action-cost upper bound.
            cover_cost = route_length(self.session.position, [q for q, _ in pieces]) / 5 + 3 * len(pieces) + 2
            if target.no_signal_streak >= 2 or self.session.deadline - time.monotonic() < 30:
                self.adaptive_cover(target, pieces)
                return
            q, cost = self.planned_measurement(target, attempt)
            if cover_cost <= cost:
                self.adaptive_cover(target, pieces)
                return
            self.measure(target, q)
            self.share_measurement(q)
        if not target.cleared:
            self.adaptive_cover(target)

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
        if self.optimized:
            return self.adaptive_localize(target)
        opportunistic = False
        for attempt in range(6):
            if target.cleared:
                return
            c, r = target.circle()
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
            if self.optimized:
                order = order_points(self.session.position, self.sites[remaining])
                index = remaining[order[0]]
            elif self.improved:
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
                if ch not in self.targets:
                    self.targets[ch] = Target(ch)
                t = self.targets[ch]
                r = self.measure(t, q)
                if r['measure_result'] == 'direction':
                    pending.append(t)
            self.visited.append(index)
            self.pending = pending
            while pending:
                if self.optimized:
                    order = order_points(self.session.position, [t.circle()[0] for t in pending])
                    target = pending.pop(order[0])
                elif self.improved:
                    target = min(pending, key=lambda t: np.linalg.norm(t.circle()[0] - self.session.position))
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
