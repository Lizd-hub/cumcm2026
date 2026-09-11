import numpy as np
from common.geometry import unit

def coverage_grid(problem):
    if problem not in (3, 4):
        raise ValueError("problem must be 3 or 4")
    axis = [-1800, -600, 600, 1800] if problem == 3 else list(range(-2100, 2101, 600))
    routes = []
    for xs in (axis, axis[::-1]):
        for ys in (axis, axis[::-1]):
            routes.append([(x, y) for i, x in enumerate(xs) for y in (ys if i%2 == 0 else ys[::-1])])
    return min(routes, key=lambda r: (np.linalg.norm(r[0]), r[0]))

def optical_grid(observation):
    e = unit(observation.bearing_deg)
    ep = np.array([-e[1], e[0]])
    return [np.array(observation.position)+20*k*e+20*l*ep for k in range(76)
            for l in (range(-2, 3) if k%2 == 0 else range(2, -3, -1))]
