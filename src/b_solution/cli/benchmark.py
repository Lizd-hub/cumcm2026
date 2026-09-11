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


def run_case(seed, question, radius='random', error='smooth', stress=False, model='optimized'):
    """Record failures as cases too; never stop the benchmark on one bad run."""
    sim = OfflineSimulator(seed, question == 4, radius, error, stress)
    session = Session(sim)
    solver = Solver(session, question == 4, model != 'baseline', optimized=model == 'optimized')
    start = time.perf_counter()
    failure = None
    try:
        result = solver.run()
    except Exception as exc:
        failure = f'{type(exc).__name__}: {exc}'
        result = {'cleared': len(solver.cleared), 'virtual_time_s': session.virtual_time,
                  'average_time_s': session.virtual_time / len(solver.cleared) if solver.cleared else None,
                  'fallbacks': solver.fallbacks, **session.stats}
        if session.started:
            try:
                session.exit()
            except Exception as exit_error:
                result['exit_error'] = str(exit_error)
    result.update(question=question, seed=seed, model=model,
                  wall_time_s=time.perf_counter() - start, **sim.evaluate())
    reconstructed = (result['distance_m'] / 5 + 5 * result['measurements'] + result['switches']
                     + 5 * result['clear_success'] + 3 * result['clear_failed'])
    if abs(reconstructed - result['virtual_time_s']) >= .002:
        failure = (failure + '; ' if failure else '') + 'Virtual cost reconstruction mismatch'
    result['completed'] = failure is None and result['cleared_truth'] == result['total'] == result['cleared']
    result['failure_reason'] = failure if failure else (None if result['completed'] else 'Incomplete clearing')
    return result, sim, session, solver


def summarize_group(group):
    successful = [r['average_time_s'] for r in group if r['completed']]
    return {'cases': len(group), 'complete_success_rate': sum(r['completed'] for r in group) / len(group),
            'clear_fraction': min(r['clear_fraction'] for r in group),
            'mean_case_average_s': float(np.mean(successful)) if successful else None,
            'median_case_average_s': float(np.median(successful)) if successful else None,
            'p95_case_average_s': float(np.percentile(successful, 95)) if successful else None,
            'max_case_average_s': max(successful, default=None),
            'mean_measurements': float(np.mean([r['measurements'] for r in group])),
            'mean_distance_m': float(np.mean([r['distance_m'] for r in group])),
            'mean_failed_clears': float(np.mean([r['clear_failed'] for r in group])),
            'max_wall_time_s': max(r['wall_time_s'] for r in group),
            'failures': [{'seed': r['seed'], 'reason': r['failure_reason']} for r in group if not r['completed']]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=int, default=12)
    parser.add_argument('--output', default='outputs/benchmarks')
    parser.add_argument('--seed-start', type=int, default=0)
    parser.add_argument('--models', nargs='+', choices=['baseline', 'improved', 'optimized'],
                        default=['improved', 'optimized'])
    parser.add_argument('--stress-cases', type=int, default=4)
    parser.add_argument('--extended', action='store_true', help='Also test discontinuous and zero spatial errors')
    args = parser.parse_args()
    if args.cases < 1 or args.stress_cases < 1:
        parser.error('Case counts must be positive.')
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    checks = validate()
    rows, examples = [], []
    configs = [('random_smooth', 'random', 'smooth', False),
               ('minrange_extreme_boundary', 'min', 'extreme', True)]
    if args.extended:
        configs += [('minrange_hash_interior', 'min', 'hash', False),
                    ('minrange_zero_interior', 'min', 'zero', False)]
    for q in (3, 4):
        for config, radius, error, stress in configs:
            count = args.cases if not stress else min(args.stress_cases, args.cases)
            for seed in range(args.seed_start, args.seed_start + count):
                for model in args.models:
                    result, sim, session, solver = run_case(seed, q, radius, error, stress, model)
                    result['scenario'] = config
                    rows.append(result)
                    if seed == args.seed_start and model == args.models[-1]:
                        examples.append({'question': q, 'scenario': config, 'sources': sim.export_truth_for_local_plot(),
                                         'path': sim.path, 'sites': solver.sites.tolist(), 'result': result,
                                         'records': session.records})
                    print(f"Q{q} {config} seed={seed} {result['model']}: {result['cleared']}/{result['total']}, "
                          f"avg={result['average_time_s']}s, wall={result['wall_time_s']:.2f}s, "
                          f"completed={result['completed']}", flush=True)
                    (out / 'raw_results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    summaries = []
    for q in (3, 4):
        for scenario, *_ in configs:
            for model in args.models:
                group = [r for r in rows if r['question'] == q and r['scenario'] == scenario and r['model'] == model]
                summaries.append({'question': q, 'scenario': scenario, 'model': model, **summarize_group(group)})
    (out / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'validation.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    q2 = second_point_demo()
    (out / 'q2_candidates.json').write_text(json.dumps(q2, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(summaries, ensure_ascii=False))


if __name__ == '__main__':
    main()
