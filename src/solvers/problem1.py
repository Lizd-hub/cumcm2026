"""问题一：交会区域直径与包围圆。"""
import argparse
from dataclasses import asdict
import numpy as np
from common.models import Observation
from common.geometry import bearing_halfplanes, halfplane_region, describe_polygon
from common.logging_io import read_json, write_json

def solve(observations, delta_deg=1.0):
    observations = [o if isinstance(o, Observation) else Observation(tuple(o["position"]), o["bearing_deg"]) for o in observations]
    constraints = [bearing_halfplanes(o, delta_deg) for o in observations]
    A = np.vstack([h[0] for h in constraints]) if constraints else np.empty((0,2))
    b = np.concatenate([h[1] for h in constraints]) if constraints else np.empty(0)
    result = asdict(halfplane_region(A, b))
    triangle = [[0,0],[100,0],[50,50*np.sqrt(3)]]
    result.update(observations=[asdict(o) for o in observations], delta_deg=delta_deg,
                  counterexample=asdict(describe_polygon(triangle)),
                  same_diameter_circle_always_covers=False, source="input_observations")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--output", default="outputs/problem1.json")
    args = parser.parse_args()
    data = read_json(args.input) if args.input else {"observations":[
        {"position":[-400,0],"bearing_deg":30},{"position":[400,0],"bearing_deg":150}]}
    result = solve(data["observations"], data.get("delta_deg",1.0))
    if not args.input:
        result["source"] = "constructed"
    write_json(args.output, result)

if __name__ == "__main__":
    main()
