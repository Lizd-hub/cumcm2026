"""配对离线实验：默认两类场景、20 个种子、两种策略。"""
import argparse
from dataclasses import replace
from pathlib import Path
from common.client import Client
from common.config import Config
from common.search import solve_search
from common.logging_io import save_run,write_json
from experiments.simulator import random_scene

def run(output="outputs/benchmark",trials=20,start_seed=20260910):
    output = Path(output)
    summaries = []
    for problem in (3,4):
        for seed in range(start_seed,start_seed+trials):
            for baseline in (True,False):
                strategy = "baseline" if baseline else "active"
                simulator = random_scene(seed,problem)
                config = replace(Config(),seed=seed,baseline=baseline)
                result = solve_search(problem,Client(simulator),config)
                evaluation = simulator.evaluate()
                result.seed = seed
                result.true_count = evaluation["true_count"]
                result.cleared_fraction = evaluation["true_cleared_count"]/result.true_count
                name = f"p{problem}_{seed}_{strategy}"
                save_run(output/(name+".json"),result)
                write_json(output/(name+".evaluation.json"),evaluation)
                row = dict(problem=problem,seed=seed,strategy=strategy,source="offline",
                           complete=result.complete,cleared_count=result.cleared_count,true_count=result.true_count,
                           cleared_fraction=result.cleared_fraction,virtual_time_s=result.virtual_time_s,
                           average_time_s=result.average_time_s,real_time_s=result.real_time_s,reason=result.reason)
                summaries.append(row)
                write_json(output/"summary.json",summaries)
                print(f"{name}: complete={result.complete} T={result.virtual_time_s:.1f}s runtime={result.real_time_s:.2f}s",flush=True)
    return summaries

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default="outputs/benchmark")
    parser.add_argument("--trials",type=int,default=20)
    parser.add_argument("--start-seed",type=int,default=20260910)
    args=parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    run(args.output,args.trials,args.start_seed)

if __name__ == "__main__":
    main()
