"""有界误差几何。圆盘全部使用外接多边形，采样不用于安全证明。"""
from itertools import combinations
import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull
from legacy_solution.common.models import GeometryResult

EPS = 1e-6


def unit(deg):
    a = np.deg2rad(deg)
    return np.array([np.cos(a), np.sin(a)])


def bearing_halfplanes(observation, delta=1.01):
    a, b = unit(observation.bearing_deg-delta), unit(observation.bearing_deg+delta)
    A = np.array([[a[1], -a[0]], [-b[1], b[0]]])
    return A, A @ np.asarray(observation.position)


def disk_halfplanes(center, radius, sides=128):
    a = np.arange(sides)*2*np.pi/sides
    A = np.column_stack([np.cos(a), np.sin(a)])
    return A, A @ np.asarray(center)+radius


def disk_polygon(center, radius, sides=128):
    a = (np.arange(sides)+0.5)*2*np.pi/sides
    return np.asarray(center)+radius/np.cos(np.pi/sides)*np.column_stack([np.cos(a), np.sin(a)])


def clip(poly, A, b):
    poly = np.asarray(poly, dtype=float).reshape(-1, 2)
    for normal, bound in zip(A, b):
        if len(poly) == 0:
            return poly
        values = poly @ normal-bound
        inside = values <= EPS
        if inside.all():
            continue
        out = []
        for i in range(len(poly)):
            j = (i+1) % len(poly)
            if inside[i]:
                out.append(poly[i])
            if inside[i] != inside[j]:
                t = values[i]/(values[i]-values[j])
                out.append(poly[i]+t*(poly[j]-poly[i]))
        poly = np.asarray(out).reshape(-1, 2)
    return poly


def hull(points):
    points = np.unique(np.round(np.asarray(points).reshape(-1, 2), 9), axis=0)
    if len(points) <= 2:
        return points
    if np.linalg.matrix_rank(points-points[0], tol=1e-8) < 2:
        d = np.linalg.norm(points[:, None]-points[None, :], axis=2)
        i, j = np.unravel_index(d.argmax(), d.shape)
        return points[[i, j]]
    return points[ConvexHull(points).vertices]


def circle_three(a, b, c):
    M = 2*np.array([b-a, c-a])
    if abs(np.linalg.det(M)) < 1e-12:
        return None
    center = np.linalg.solve(M, [np.dot(b-a, b-a), np.dot(c-a, c-a)])+a
    return center, float(np.linalg.norm(center-a))


def enclosing_circle(points, seed=20260910):
    """固定顺序随机增量法；最终半径重新覆盖全部输入点。"""
    p = np.asarray(points, dtype=float)
    if len(p) == 0:
        raise ValueError("空集无包围圆")
    p = p[np.random.default_rng(seed).permutation(len(p))]
    center, radius = p[0].copy(), 0.0
    for i, a in enumerate(p):
        if np.linalg.norm(a-center) <= radius+1e-9:
            continue
        center, radius = a.copy(), 0.0
        for j, b in enumerate(p[:i]):
            if np.linalg.norm(b-center) <= radius+1e-9:
                continue
            center, radius = (a+b)/2, np.linalg.norm(a-b)/2
            for c in p[:j]:
                if np.linalg.norm(c-center) <= radius+1e-9:
                    continue
                result = circle_three(a, b, c)
                if result is None:
                    pair = max(combinations([a, b, c], 2), key=lambda x: np.linalg.norm(x[0]-x[1]))
                    center, radius = (pair[0]+pair[1])/2, np.linalg.norm(pair[0]-pair[1])/2
                else:
                    center, radius = result
    radius = float(np.max(np.linalg.norm(p-center, axis=1)))
    return center, radius


def describe_polygon(points):
    p = hull(points)
    if not len(p):
        return GeometryResult("empty", [])
    dist = np.linalg.norm(p[:, None]-p[None, :], axis=2)
    i, j = np.unravel_index(dist.argmax(), dist.shape)
    center, radius = enclosing_circle(p)
    return GeometryResult("bounded", p.tolist(), float(dist[i, j]), p[[i, j]].tolist(), center.tolist(), radius)


def halfplane_region(A, b):
    A, b = np.asarray(A, float).reshape(-1, 2), np.asarray(b, float)
    if not len(A):
        return GeometryResult("unbounded", [], float("inf"))
    def lp(c):
        return linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)]*2, method="highs")
    feasible = lp([0, 0])
    if feasible.status == 2:
        return GeometryResult("empty", [])
    if not feasible.success:
        raise ArithmeticError(feasible.message)
    extrema = [lp(c) for c in [[1, 0], [-1, 0], [0, 1], [0, -1]]]
    if any(x.status == 3 for x in extrema):
        return GeometryResult("unbounded", [], float("inf"))
    if any(not x.success for x in extrema):
        raise ArithmeticError("坐标极值求解失败")
    points = [x.x for x in extrema]
    for i, j in combinations(range(len(A)), 2):
        M = A[[i, j]]
        if abs(np.linalg.det(M)) <= 1e-14:
            continue
        x = np.linalg.solve(M, b[[i, j]])
        if np.all(A @ x <= b+EPS):
            points.append(x)
    return describe_polygon(points)


def update_outer(poly, observation, config):
    poly = clip(poly, *bearing_halfplanes(observation, config.delta_deg))
    return clip(poly, *disk_halfplanes(observation.position, 1500, config.disk_sides))
