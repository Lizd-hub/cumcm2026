"""Bearing-only geometry. All lengths are metres; public angles are degrees."""
from itertools import combinations
from functools import lru_cache
import math
import numpy as np
from scipy.optimize import linprog

DELTA_DEG = 1.005  # Conservative allowance for the protocol's 0.01 degree rounding.


def unit(angle_deg):
    a = math.radians(angle_deg)
    return np.array([math.cos(a), math.sin(a)])


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def wedge_halfplanes(position, bearing_deg, delta_deg=DELTA_DEG):
    """Return A,b with A @ source <= b for a FORWARD bearing wedge."""
    s = np.asarray(position, dtype=float)
    lo, hi = unit(bearing_deg - delta_deg), unit(bearing_deg + delta_deg)
    a = np.array([[lo[1], -lo[0]], [-hi[1], hi[0]]])
    return a, a @ s


def clip(poly, normal, bound, tol=1e-8):
    """Sutherland-Hodgman clipping of an ordered convex polygon."""
    p = np.asarray(poly, dtype=float).reshape(-1, 2)
    if not len(p):
        return p
    out = []
    prev, fp = p[-1], float(p[-1] @ normal - bound)
    for cur in p:
        fc = float(cur @ normal - bound)
        ip, ic = fp <= tol, fc <= tol
        if ip != ic:
            den = fp - fc
            if abs(den) > 1e-15:
                out.append(prev + (fp / den) * (cur - prev))
        if ic:
            out.append(cur)
        prev, fp = cur, fc
    if not out:
        return np.empty((0, 2))
    ans = [np.asarray(out[0])]
    for x in out[1:]:
        if np.linalg.norm(x - ans[-1]) > 1e-8:
            ans.append(x)
    if len(ans) > 1 and np.linalg.norm(ans[0] - ans[-1]) < 1e-8:
        ans.pop()
    return np.array(ans)


def clip_all(poly, a, b):
    poly = np.asarray(poly, float).reshape(-1, 2)
    if not len(poly):
        return poly
    a, b = np.asarray(a), np.asarray(b)
    distances = a @ poly.T - b[:, None]
    if np.any(np.all(distances > 1e-8, axis=1)):
        return np.empty((0, 2))
    # Constraints already satisfied by every original vertex remain satisfied
    # by every subsequent convex subset. Skip them in a single NumPy operation.
    active = np.any(distances > 1e-8, axis=1)
    for normal, bound in zip(a[active], b[active]):
        poly = clip(poly, normal, bound)
        if not len(poly):
            break
    return poly


def outer_disk(center, radius, sides=64):
    """Circumscribed, NOT inscribed: never discard a feasible true source."""
    angles = np.arange(sides) * 2 * np.pi / sides
    return np.asarray(center) + radius / np.cos(np.pi / sides) * np.c_[np.cos(angles), np.sin(angles)]


def disk_halfplanes(center, radius, sides=64):
    a = disk_normals(sides)
    return a, radius + a @ np.asarray(center)


@lru_cache(maxsize=8)
def disk_normals(sides):
    angles = (np.arange(sides) + .5) * 2 * np.pi / sides
    a = np.c_[np.cos(angles), np.sin(angles)]
    a.setflags(write=False)
    return a


def observe(poly, position, bearing_deg, delta_deg=DELTA_DEG):
    a, b = wedge_halfplanes(position, bearing_deg, delta_deg)
    p = clip_all(poly, a, b)
    a, b = disk_halfplanes(position, 1500.)
    p = clip_all(p, a, b)
    # An exact outer rectangle around this truncated wedge limits fallback size.
    u, v = unit(bearing_deg), unit(bearing_deg + 90.)
    a = np.array([u, -u, v, -v])
    b = np.array([1500., 0., 1500 * math.sin(math.radians(delta_deg)),
                  1500 * math.sin(math.radians(delta_deg))]) + a @ np.asarray(position)
    return clip_all(p, a, b)


def convex_hull(points):
    points = sorted(set(map(tuple, np.asarray(points, dtype=float))))
    if len(points) <= 1:
        return np.asarray(points).reshape(-1, 2)
    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and cross(np.subtract(h[-1], h[-2]), np.subtract(q, h[-1])) <= 1e-10:
                h.pop()
            h.append(q)
        return h
    return np.array(half(points)[:-1] + half(points[::-1])[:-1])


def halfplane_polygon(a, b):
    """Exact halfplane model for Q1, with explicit empty/unbounded states.

    Boundary-pair enumeration is deliberately simple: O(H^3). No artificial
    bounding box is used to conceal an unbounded intersection.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    feasible = linprog([0., 0.], A_ub=a, b_ub=b, bounds=[(None, None)] * 2, method='highs')
    if feasible.status == 2:
        return 'empty', np.empty((0, 2))
    if not feasible.success:
        raise RuntimeError('Feasibility solver failed: ' + feasible.message)
    for objective in ([1, 0], [-1, 0], [0, 1], [0, -1]):
        r = linprog(objective, A_ub=a, b_ub=b, bounds=[(None, None)] * 2, method='highs')
        if r.status == 3:
            return 'unbounded', np.empty((0, 2))
        if not r.success:
            raise RuntimeError('Boundedness solver failed: ' + r.message)
    vertices = []
    for i, j in combinations(range(len(b)), 2):
        mat = a[[i, j]]
        if abs(np.linalg.det(mat)) < 1e-12:
            continue
        q = np.linalg.solve(mat, b[[i, j]])
        if np.all(a @ q <= b + 1e-7):
            vertices.append(q)
    if not vertices:
        raise RuntimeError('Bounded region has no numerically recoverable vertices.')
    # Merge numerically coincident vertices before forming a hull.
    unique = []
    for q in vertices:
        if not any(np.linalg.norm(q - p) < 1e-6 for p in unique):
            unique.append(q)
    return 'bounded', convex_hull(unique)


def diameter_brute(poly):
    p = np.asarray(poly)
    if not len(p):
        raise ValueError('An empty region has no localization diameter.')
    d2 = np.sum((p[:, None] - p[None, :]) ** 2, axis=-1)
    i, j = np.unravel_index(np.argmax(d2), d2.shape)
    return math.sqrt(float(d2[i, j])), (int(i), int(j))


def diameter_calipers(poly):
    """O(m) on a convex counterclockwise polygon; includes parallel-edge ties."""
    p = np.asarray(poly)
    n = len(p)
    if n <= 2:
        return diameter_brute(p)
    best, pair, j = -1., (0, 0), 1
    for i in range(n):
        ni = (i + 1) % n
        edge = p[ni] - p[i]
        area = lambda k: abs(cross(edge, p[k] - p[i]))
        for _ in range(n):
            nj = (j + 1) % n
            if area(nj) > area(j) + 1e-9:
                j = nj
            else:
                break
        candidates = [j]
        if abs(area((j + 1) % n) - area(j)) < 1e-9:
            candidates.append((j + 1) % n)
        for u in (i, ni):
            for v in candidates:
                d2 = float(np.sum((p[u] - p[v]) ** 2))
                if d2 > best:
                    best, pair = d2, (u, v)
    return math.sqrt(best), pair


def minimum_circle_reference(poly):
    """Small-polygon MEC by all 2/3 support points, independently auditable.

    For this problem bearing intersections normally have few vertices. This
    transparent O(m^4) implementation is not advertised as Welzl's algorithm.
    """
    p = np.asarray(poly, float)
    if not len(p):
        raise ValueError('Empty feasible set: check units, wrapping and data.')
    if len(p) == 1:
        return p[0].copy(), 0.
    best_c, best_r = p.mean(axis=0), float('inf')
    def consider(c):
        nonlocal best_c, best_r
        # Use actual maximum vertex distance, so numerical support-circle
        # rounding cannot understate the reported enclosing radius.
        r = float(np.max(np.linalg.norm(p - c, axis=1)))
        if r < best_r:
            best_c, best_r = c, r
    for i, j in combinations(range(len(p)), 2):
        consider((p[i] + p[j]) / 2)
    for i, j, k in combinations(range(len(p)), 3):
        q = p[[i, j, k]] - p[i]
        mat = 2 * q[1:]
        if abs(np.linalg.det(mat)) < 1e-10:
            continue
        c = p[i] + np.linalg.solve(mat, np.sum(q[1:] ** 2, axis=1))
        consider(c)
    return best_c, best_r


def minimum_circle(poly):
    """Incremental enclosing circle, with deterministic local shuffling.

    Final vertex verification always gives a conservative radius. The exhaustive
    reference remains available for numerical degeneracies and independent tests.
    """
    points = np.asarray(poly, float).reshape(-1, 2)
    if not len(points):
        raise ValueError('Empty feasible set: check units, wrapping and data.')
    if not np.all(np.isfinite(points)):
        raise ValueError('Non-finite circle input.')
    if len(points) <= 2:
        c = points.mean(axis=0)
        return c, float(np.linalg.norm(points - c, axis=1).max())
    p = points[np.random.default_rng(0).permutation(len(points))]
    c, r2 = p[0].copy(), 0.
    for i, a in enumerate(p):
        if float((a - c) @ (a - c)) <= r2 + 1e-9:
            continue
        c, r2 = a.copy(), 0.
        for j in range(i):
            b = p[j]
            if float((b - c) @ (b - c)) <= r2 + 1e-9:
                continue
            c = (a + b) / 2
            r2 = float((a - c) @ (a - c))
            for k in range(j):
                d = p[k]
                if float((d - c) @ (d - c)) <= r2 + 1e-9:
                    continue
                u, v = b - a, d - a
                determinant = cross(u, v)
                if abs(determinant) <= 1e-12 * max(1., np.linalg.norm(u) * np.linalg.norm(v)):
                    return minimum_circle_reference(points)
                uu, vv = float(u @ u), float(v @ v)
                c = a + np.array([v[1] * uu - u[1] * vv,
                                   u[0] * vv - v[0] * uu]) / (2 * determinant)
                r2 = float((a - c) @ (a - c))
    radius = float(np.linalg.norm(points - c, axis=1).max())
    if not np.isfinite(radius) or radius > math.sqrt(r2) + 1e-5:
        return minimum_circle_reference(points)
    return c, radius


def safe_second_point(point, first_position, first_bearing, delta_deg=DELTA_DEG):
    """Membership of a universal sufficient reception lens for an omni source."""
    s = np.asarray(first_position)
    centers = np.array([s, s + 1000 * unit(first_bearing - delta_deg),
                        s + 1000 * unit(first_bearing + delta_deg)])
    return bool(np.max(np.linalg.norm(centers - np.asarray(point), axis=1)) <= 1000 + 1e-8)


def second_point_demo(delta_deg=DELTA_DEG):
    """Finite scenario minimax example, NOT a continuous global optimum."""
    p0 = observe(outer_disk([0, 0], 1800), [0, 0], 0, delta_deg)
    sources = [d * unit(a) for d in np.linspace(10, 1500, 17)
               for a in (-delta_deg, 0, delta_deg)]
    results = []
    for x in (300, 450, 600, 750, 900):
        for y in (200, 350, 500, 650, 800):
            q = np.array([x, y], float)
            if not safe_second_point(q, [0, 0], 0, delta_deg):
                continue
            worst = 0.
            for g in sources:
                if np.linalg.norm(q - g) <= 5:
                    r = 5.
                    worst = max(worst, r)
                    continue
                theta = math.degrees(math.atan2(g[1] - q[1], g[0] - q[0]))
                for err in (-1., 0., 1.):
                    p = observe(p0, q, round((theta + err) % 360, 2) % 360, delta_deg)
                    _, r = minimum_circle(p)
                    worst = max(worst, r)
            results.append({'x': x, 'y': y, 'move_s': float(np.linalg.norm(q) / 5),
                            'sample_worst_radius_m': worst})
    return sorted(results, key=lambda x: x['sample_worst_radius_m'])
