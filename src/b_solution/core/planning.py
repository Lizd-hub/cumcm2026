"""Heuristic reception planning and conservative finite optical covers."""
import math
import numpy as np
from .geometry import clip, minimum_circle, unit


def route_length(start, route):
    if not len(route):
        return 0.
    return float(np.linalg.norm(np.diff(np.vstack([start, route]), axis=0), axis=1).sum())


def order_points(start, points):
    """Short open route; every input point is retained, no return leg required."""
    points = np.asarray(points).reshape(-1, 2)
    if len(points) < 2:
        return list(range(len(points)))
    remaining = list(range(len(points)))
    greedy, current = [], np.asarray(start)
    while remaining:
        k = min(remaining, key=lambda i: float((points[i] - current) @ (points[i] - current)))
        remaining.remove(k)
        greedy.append(k)
        current = points[k]
    routes = [greedy, greedy[::-1]]
    for axis in (0, 1):
        indices = list(np.argsort(points[:, axis]))
        routes.extend([indices, indices[::-1]])
    route = min(routes, key=lambda ix: route_length(start, points[ix]))
    # Bounded open-path 2-opt; local improvements cannot lose coverage.
    for _ in range(2):
        changed = False
        for i in range(len(route) - 1):
            a = np.asarray(start) if i == 0 else points[route[i - 1]]
            b = points[route[i]]
            for j in range(i + 1, len(route)):
                c = points[route[j]]
                old, new = np.linalg.norm(a - b), np.linalg.norm(a - c)
                if j + 1 < len(route):
                    d = points[route[j + 1]]
                    old += np.linalg.norm(c - d)
                    new += np.linalg.norm(b - d)
                if new + 1e-7 < old:
                    route[i:j + 1] = reversed(route[i:j + 1])
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    return route


def excluded(poly, exclusions):
    # A whole convex piece lies inside a disk iff all its vertices do.
    # Strict margin avoids removing boundary candidates through rounding.
    return any(np.max(np.linalg.norm(poly - p, axis=1)) < radius - 1e-6
               for p, radius in exclusions)


def optical_pieces(poly, exclusions=()):
    """Bisect a conservative polygon until each piece has radius <=19.5 m.

    Every split retains both closed halves. Exclusions remove only pieces
    wholly inside a certified empty disk. No sampled position is a certificate.
    """
    pending, pieces = [np.asarray(poly)], []
    while pending:
        p = pending.pop()
        if not len(p) or excluded(p, exclusions):
            continue
        c, r = minimum_circle(p)
        if r <= 19.5:
            pieces.append((c, p))
            continue
        centered = p - p.mean(axis=0)
        _, vectors = np.linalg.eigh(centered.T @ centered)
        axis = vectors[:, -1]
        projection = p @ axis
        mid = (projection.min() + projection.max()) / 2
        pending.extend([clip(p, axis, mid), clip(p, -axis, -mid)])
    return pieces


def reception_probabilities(target, source, points, mixed):
    """Finite (radius, emission-axis) hypotheses, for ranking only.

    Both omni and directional hypotheses survive in Q4. Positive and negative
    readings condition these hypotheses without cutting the certified polygon.
    """
    points = np.asarray(points).reshape(-1, 2)
    positive = np.array([p for p, _ in target.observations])
    distances = np.linalg.norm(positive - source, axis=1)
    low = max(1000., float(distances.max()))
    if low > 1500. + 1e-6:
        return np.full(len(points), .5)  # Outer approximation, not an exact disk.
    radii = np.unique([min(low + 1e-6, 1500.), (low + 1500.) / 2, 1500.])
    axes = [np.zeros(2)]  # Zero axis represents omnidirectional emission.
    if mixed:
        angles = list(np.arange(0., 360., 15.))
        for p in list(positive) + target.negative:
            d = p - source
            a = math.degrees(math.atan2(d[1], d[0]))
            angles.extend([a - 90 - .01, a - 90 + .01, a + 90 - .01, a + 90 + .01])
        axes += [unit(a) for a in angles]
    axes = np.array(axes)
    axes = axes[np.all((positive - source) @ axes.T >= -1e-7, axis=0)]
    valid = np.ones((len(axes), len(radii)), dtype=bool)
    if target.negative:
        negative = np.array(target.negative) - source
        in_angle = negative @ axes.T >= 0
        in_range = np.linalg.norm(negative, axis=1)[:, None] <= radii
        valid &= ~np.any(in_angle[:, :, None] & in_range[:, None, :], axis=0)
    if not np.any(valid):
        return np.full(len(points), .5)
    offsets = points - source
    reception = ((offsets @ axes.T >= 0)[:, :, None]
                 & (np.linalg.norm(offsets, axis=1)[:, None] <= radii)[:, None, :])
    return (reception & valid).sum(axis=(1, 2)) / valid.sum()


def reception_probability(target, source, point, mixed):
    return float(reception_probabilities(target, source, [point], mixed)[0])
