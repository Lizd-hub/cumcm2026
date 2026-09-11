"""Paired independent local scenarios. Never label these official results."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from ..infrastructure.offline_simulator import OfflineSimulator
from ..infrastructure.protocol import Session
from ..core.solver import Solver
from .validate import validate
from ..core.geometry import second_point_demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=int, default=12)
    parser.add_argument('--output', default='outputs/benchmarks')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    checks = validate()
    rows, examples = [], []
    configs = [('random_smooth', 'random', 'smooth', False),
               ('minrange_extreme_boundary', 'min', 'extreme', True)]
    for q in (3, 4):
        for config, radius, error, stress in configs:
            count = args.cases if not stress else min(4, args.cases)
            for seed in range(count):
                for improved in (False, True):
                    sim = OfflineSimulator(seed, q == 4, radius, error, stress)
                    session = Session(sim)
                    solver = Solver(session, q == 4, improved)
                    start = time.perf_counter()
                    result = solver.run()
                    result.update(question=q, seed=seed, model='improved' if improved else 'baseline',
                                  scenario=config, wall_time_s=time.perf_counter() - start, **sim.evaluate())
                    # Independently reconstruct virtual costs from accepted actions.
                    reconstructed = (result['distance_m'] / 5 + 5 * result['measurements'] + result['switches']
                                     + 5 * result['clear_success'] + 3 * result['clear_failed'])
                    assert abs(reconstructed - result['virtual_time_s']) < .002
                    assert result['cleared_truth'] == result['total'] == result['cleared']
                    rows.append(result)
                    if seed == 0 and improved:
                        examples.append({'question': q, 'scenario': config, 'sources': sim.export_truth_for_local_plot(),
                                         'path': sim.path, 'sites': solver.sites.tolist(), 'result': result,
                                         'records': session.records})
                    print(f"Q{q} {config} seed={seed} {result['model']}: {result['cleared']}/{result['total']}, "
                          f"avg={result['average_time_s']:.2f}s, wall={result['wall_time_s']:.2f}s", flush=True)
                    (out / 'raw_results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    summaries = []
    for q in (3, 4):
        for scenario, *_ in configs:
            for model in ('baseline', 'improved'):
                group = [r for r in rows if r['question'] == q and r['scenario'] == scenario and r['model'] == model]
                summaries.append({'question': q, 'scenario': scenario, 'model': model, 'cases': len(group),
                                  'clear_fraction': min(r['clear_fraction'] for r in group),
                                  'mean_case_average_s': float(np.mean([r['average_time_s'] for r in group])),
                                  'median_case_average_s': float(np.median([r['average_time_s'] for r in group])),
                                  'max_case_average_s': max(r['average_time_s'] for r in group),
                                  'mean_measurements': float(np.mean([r['measurements'] for r in group])),
                                  'mean_distance_m': float(np.mean([r['distance_m'] for r in group])),
                                  'mean_failed_clears': float(np.mean([r['clear_failed'] for r in group])),
                                  'max_wall_time_s': max(r['wall_time_s'] for r in group)})
    (out / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'validation.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    q2 = second_point_demo()
    (out / 'q2_candidates.json').write_text(json.dumps(q2, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(summaries, ensure_ascii=False))


if __name__ == '__main__':
    main()
