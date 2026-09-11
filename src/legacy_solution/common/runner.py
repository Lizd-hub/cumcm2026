"""问题三、四命令行的公共参数；默认只运行离线场景。"""
import argparse
from pathlib import Path
from legacy_solution.common.client import Client,HttpTransport
from legacy_solution.common.config import Config
from legacy_solution.common.logging_io import read_json,save_run,write_json

def run_cli(problem,solve):
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend",choices=["offline","http"],default="offline")
    parser.add_argument("--seed",type=int,default=20260910)
    parser.add_argument("--scene",help="离线真值场景 JSON，仅传入模拟器")
    parser.add_argument("--baseline",action="store_true")
    parser.add_argument("--robot-id")
    parser.add_argument("--base-url",default="http://127.0.0.1:2026")
    parser.add_argument("--source",choices=["official_practice","official_formal"],default="official_practice")
    parser.add_argument("--output",default=f"outputs/problem{problem}.json")
    args = parser.parse_args()
    config = Config(seed=args.seed,baseline=args.baseline)
    simulator = None
    if args.backend == "http":
        if not args.robot_id:
            parser.error("--robot-id is required for HTTP")
        client = Client(HttpTransport(args.base_url),args.robot_id,args.source,
                        journal=Path(args.output).with_suffix(".raw.jsonl"))
    else:
        from legacy_solution.experiments.simulator import random_scene,Simulator,Source
        simulator = Simulator([Source(**s) for s in read_json(args.scene)["sources"]],args.seed) if args.scene else random_scene(args.seed,problem)
        if problem == 3 and args.scene and any(s.get("heading_deg") is not None for s in read_json(args.scene)["sources"]):
            parser.error("problem 3 requires omnidirectional sources")
        client = Client(simulator)
    result = solve(client,config)
    result.seed = args.seed if simulator else None
    if simulator:
        evaluation = simulator.evaluate()
        result.true_count = evaluation["true_count"]
        result.cleared_fraction = evaluation["true_cleared_count"]/result.true_count if result.true_count else None
        write_json(Path(args.output).with_suffix(".evaluation.json"),evaluation)
    save_run(args.output,result)
    print(f"problem={problem} complete={result.complete} cleared={result.cleared_count} virtual={result.virtual_time_s:.3f}s")
