"""问题二：第二检测点候选区域与选择。"""
import argparse
from dataclasses import asdict
from common.config import Config
from common.models import Observation, ChannelState
from common.geometry import disk_polygon, update_outer
from common.localization import choose_next
from common.logging_io import read_json, write_json

def solve(observation, config=None):
    config = config or Config()
    o = observation if isinstance(observation, Observation) else Observation(tuple(observation["position"]), observation["bearing_deg"])
    outer = update_outer(disk_polygon((0,0),1800,config.disk_sides), o, config)
    target = ChannelState(1,"detected",[o],outer.tolist())
    result = choose_next(o.position,1,target,config)
    if result is None:
        result = dict(selected=None,candidates=[],outer=outer.tolist(),reason="empty_region_or_no_candidate")
    result.update(observation=asdict(o), config=asdict(config), source="input_observation")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--output", default="outputs/problem2.json")
    args = parser.parse_args()
    result = solve(read_json(args.input) if args.input else {"position":[0,0],"bearing_deg":35})
    if not args.input:
        result["source"] = "constructed"
    write_json(args.output,result)

if __name__ == "__main__":
    main()
