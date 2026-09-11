"""Run both solution implementations against identical local test cases.

The output is explicitly a shared-environment offline comparison. It is not
an official simulator score and must not be used as a formal-test record.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import time

import numpy as np

from legacy_solution.common.client import Client
from legacy_solution.common.config import Config
from legacy_solution.common.logging_io import write_json
from legacy_solution.common.search import solve_search
from legacy_solution.experiments.shared_environment import Scenario, SharedSimulator, make_scenario


def _load_b_solution():
    from b_solution.protocol import Session
    from b_solution.solver import Solver

    return Session, Solver


def _base_row(scenario: Scenario, solution: str, variant: str) -> dict:
    return {
        "problem": scenario.problem,
        "profile": scenario.profile,
        "seed": scenario.seed,
        "solution": solution,
        "variant": variant,
        "success": False,
        "complete_claimed": False,
        "true_count": len(scenario.sources),
        "cleared_count": 0,
        "virtual_time_s": None,
        "average_time_s": None,
        "wall_time_s": None,
        "measurements": None,
        "distance_m": None,
        "clear_success": None,
        "clear_failed": None,
        "coverage_sites": None,
        "fallbacks": None,
        "reason": "not_started",
        "error": None,
        "case_sha256": None,
    }


def _run_legacy(scenario: Scenario, variant: str) -> dict:
    row = _base_row(scenario, "legacy_solution", variant)
    simulator = SharedSimulator(scenario)
    client = Client(simulator)
    config = Config(seed=scenario.seed, baseline=variant == "baseline")
    started = time.perf_counter()
    try:
        result = solve_search(scenario.problem, client, config)
        evaluation = simulator.evaluate()
        row.update(
            complete_claimed=bool(result.complete),
            cleared_count=evaluation["true_cleared_count"],
            success=evaluation["true_cleared_count"] == evaluation["true_count"],
            virtual_time_s=result.virtual_time_s,
            average_time_s=result.average_time_s,
            measurements=sum(event.get("path") == "/measure" for event in result.events if event.get("kind") == "action"),
            distance_m=result.time_breakdown.get("movement", 0.0) * 5,
            clear_success=result.time_breakdown.get("clear_success", 0.0) / 5,
            clear_failed=result.time_breakdown.get("clear_failure", 0.0) / 3,
            coverage_sites=len(result.coverage),
            fallbacks=sum(event.get("phase") == "fallback" for event in result.events),
            reason=result.reason,
            case_sha256=evaluation["case_sha256"],
        )
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["reason"] = row["error"]
        row["cleared_count"] = simulator.evaluate()["true_cleared_count"]
        row["case_sha256"] = simulator.evaluate()["case_sha256"]
    row["wall_time_s"] = time.perf_counter() - started
    return row


def _run_b_solution(scenario: Scenario, variant: str) -> dict:
    Session, Solver = _load_b_solution()
    row = _base_row(scenario, "b_solution", variant)
    simulator = SharedSimulator(scenario)
    session = Session(simulator)
    solver = Solver(session, mixed=scenario.problem == 4, improved=variant != "baseline")
    started = time.perf_counter()
    try:
        result = solver.run()
        evaluation = simulator.evaluate()
        row.update(
            complete_claimed=result.get("completion_reason") in ("known_upper_bound_16", "all_uncleared_channels_scanned_at_complete_cover"),
            cleared_count=evaluation["true_cleared_count"],
            success=evaluation["true_cleared_count"] == evaluation["true_count"],
            virtual_time_s=result["virtual_time_s"],
            average_time_s=result["average_time_s"],
            measurements=result["measurements"],
            distance_m=result["distance_m"],
            clear_success=result["clear_success"],
            clear_failed=result["clear_failed"],
            coverage_sites=result["sites_planned"],
            fallbacks=result["fallbacks"],
            reason=result["completion_reason"],
            case_sha256=evaluation["case_sha256"],
        )
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["reason"] = row["error"]
        row["cleared_count"] = simulator.evaluate()["true_cleared_count"]
        row["case_sha256"] = simulator.evaluate()["case_sha256"]
        if session.started:
            try:
                session.exit()
            except Exception:
                pass
    row["wall_time_s"] = time.perf_counter() - started
    return row


def _paired(rows: list[dict]) -> list[dict]:
    pairs = []
    keys = sorted({(row["problem"], row["profile"], row["seed"], row["variant"]) for row in rows})
    for problem, profile, seed, variant in keys:
        current = {
            row["solution"]: row
            for row in rows
            if (row["problem"], row["profile"], row["seed"], row["variant"]) == (problem, profile, seed, variant)
        }
        if set(current) != {"legacy_solution", "b_solution"}:
            continue
        legacy, b = current["legacy_solution"], current["b_solution"]
        both_success = legacy["success"] and b["success"]
        if both_success:
            delta = b["virtual_time_s"] - legacy["virtual_time_s"]
            winner = "b_solution" if delta < -1e-9 else "legacy_solution" if delta > 1e-9 else "tie"
        elif legacy["success"] and not b["success"]:
            delta, winner = None, "legacy_solution"
        elif b["success"] and not legacy["success"]:
            delta, winner = None, "b_solution"
        else:
            delta, winner = None, "both_failed"
        pairs.append(
            {
                "problem": problem,
                "profile": profile,
                "seed": seed,
                "variant": variant,
                "legacy_success": legacy["success"],
                "b_success": b["success"],
                "both_success": both_success,
                "legacy_time_s": legacy["virtual_time_s"],
                "b_time_s": b["virtual_time_s"],
                "b_minus_legacy_time_s": delta,
                "winner": winner,
                "legacy_reason": legacy["reason"],
                "b_reason": b["reason"],
            }
        )
    return pairs


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _summary(rows: list[dict]) -> list[dict]:
    groups = sorted({(r["problem"], r["profile"], r["solution"], r["variant"]) for r in rows})
    output = []
    for problem, profile, solution, variant in groups:
        group = [r for r in rows if (r["problem"], r["profile"], r["solution"], r["variant"]) == (problem, profile, solution, variant)]
        successful = [r for r in group if r["success"]]
        times = [r["virtual_time_s"] for r in successful if r["virtual_time_s"] is not None]
        output.append(
            {
                "problem": problem,
                "profile": profile,
                "solution": solution,
                "variant": variant,
                "cases": len(group),
                "successes": len(successful),
                "success_rate": len(successful) / len(group) if group else None,
                "mean_time_s_success": _mean(times),
                "median_time_s_success": float(np.median(times)) if times else None,
                "p90_time_s_success": float(np.percentile(times, 90)) if times else None,
                "mean_cleared_count": _mean([r["cleared_count"] for r in group]),
                "mean_measurements": _mean([r["measurements"] for r in group if r["measurements"] is not None]),
                "mean_distance_m": _mean([r["distance_m"] for r in group if r["distance_m"] is not None]),
                "mean_clear_failed": _mean([r["clear_failed"] for r in group if r["clear_failed"] is not None]),
                "mean_wall_time_s": _mean([r["wall_time_s"] for r in group]),
            }
        )
    return output


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _analysis(summary: list[dict], pairs: list[dict], scenarios: list[dict]) -> str:
    variants = sorted({row["variant"] for row in summary})
    lines = [
        "# 两种方案统一测试比较报告",
        "",
        "> 本报告由同一组离线场景、同一误差场和同一动作计费规则生成；不代表官方演练或正式测试成绩。",
        "",
        f"共测试 {len(scenarios)} 个场景。每个场景由两个方案分别从初始位置和初始频道启动，真值摘要相同。",
        "",
        "## 汇总",
        "",
        "|问题|场景|方案|变体|成功率|成功案例平均虚拟时间/s|平均测量次数|平均移动距离/m|平均失败清除次数|",
        "|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"|{row['problem']}|{row['profile']}|{row['solution']}|{row['variant']}|{row['success_rate']:.1%}|"
            f"{row['mean_time_s_success'] if row['mean_time_s_success'] is not None else '—'}|"
            f"{row['mean_measurements'] if row['mean_measurements'] is not None else '—'}|"
            f"{row['mean_distance_m'] if row['mean_distance_m'] is not None else '—'}|"
            f"{row['mean_clear_failed'] if row['mean_clear_failed'] is not None else '—'}|"
        )
    lines.extend(["", "## 配对结论", "", "|问题|场景|变体|两者均成功|旧版时间/s|v0.2.0 主方案时间/s|b−旧版/s|配对胜者|", "|---:|---|---|---:|---:|---:|---:|---|"])
    for row in pairs:
        lines.append(
            f"|{row['problem']}|{row['profile']}|{row['variant']}|{'是' if row['both_success'] else '否'}|"
            f"{row['legacy_time_s'] if row['legacy_time_s'] is not None else '—'}|"
            f"{row['b_time_s'] if row['b_time_s'] is not None else '—'}|"
            f"{row['b_minus_legacy_time_s'] if row['b_minus_legacy_time_s'] is not None else '—'}|{row['winner']}|"
        )
    complete_pairs = [row for row in pairs if row["both_success"] and row["b_minus_legacy_time_s"] is not None]
    lines.extend(["", "## 自动分析", ""])
    if complete_pairs:
        b_wins = sum(row["winner"] == "b_solution" for row in complete_pairs)
        legacy_wins = sum(row["winner"] == "legacy_solution" for row in complete_pairs)
        ties = len(complete_pairs) - b_wins - legacy_wins
        mean_delta = float(np.mean([row["b_minus_legacy_time_s"] for row in complete_pairs]))
        lines.append(f"在 {len(complete_pairs)} 个双方均成功的配对中，v0.2.0 主方案更快 {b_wins} 次，旧版更快 {legacy_wins} 次，持平 {ties} 次；平均时间差 b−旧版为 {mean_delta:.3f} s。")
    else:
        lines.append("没有足够的双方均成功配对，未计算时间优劣。")
    for problem in (3, 4):
        for profile in ("random", "boundary"):
            group = [r for r in pairs if r["problem"] == problem and r["profile"] == profile and r["variant"] == "active"]
            if not group:
                continue
            legacy_ok = sum(r["legacy_success"] for r in group)
            b_ok = sum(r["b_success"] for r in group)
            lines.append(f"问题{problem} / {profile}：旧版成功 {legacy_ok}/{len(group)}，v0.2.0 主方案成功 {b_ok}/{len(group)}。")
    lines.extend([
        "",
        "## 解读边界",
        "",
        "- 虚拟时间用于算法动作成本的公平比较；墙钟时间只反映本机实现和当前负载，不宜作为稳定排名依据。",
        "- boundary 是压力场景，主要用于暴露边界覆盖、定向源背向无信号和最小接收半径下的鲁棒性。",
        "- 成功率优先于时间差；某方案失败时，配对胜者按成功性判定，失败案例的时间不进入成功案例平均时间。",
    ])
    if "baseline" in variants:
        lines.append("- 两套方案的内部 baseline/active 变体均已保留，可用于区分“方案差异”和各自改进策略的收益。")
    else:
        lines.append("- 本次报告只运行 active 变体；如需同时评估两套方案各自的 baseline，请去掉命令中的 `--active-only`。")
    return "\n".join(lines) + "\n"


def run(output: str = "outputs/shared_comparison", trials: int = 10, start_seed: int = 20260910, include_baseline: bool = True) -> dict:
    if trials < 1:
        raise ValueError("trials must be positive")
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    variants = ("active", "baseline") if include_baseline else ("active",)
    scenarios = [
        make_scenario(problem, seed, profile)
        for profile in ("random", "boundary")
        for problem in (3, 4)
        for seed in range(start_seed, start_seed + trials)
    ]
    rows: list[dict] = []
    scenario_records = [scenario.as_dict() for scenario in scenarios]
    write_json(output_path / "scenarios.json", scenario_records)
    for scenario in scenarios:
        for variant in variants:
            legacy_row = _run_legacy(scenario, variant)
            b_row = _run_b_solution(scenario, variant)
            rows.extend((legacy_row, b_row))
            print(
                f"P{scenario.problem} {scenario.profile} seed={scenario.seed} {variant}: "
                f"legacy={legacy_row['cleared_count']}/{legacy_row['true_count']} "
                f"v0.2.0={b_row['cleared_count']}/{b_row['true_count']}",
                flush=True,
            )
    pairs = _paired(rows)
    summary = _summary(rows)
    write_json(output_path / "raw_results.json", rows)
    write_json(output_path / "paired_comparison.json", pairs)
    write_json(output_path / "summary.json", summary)
    _write_csv(output_path / "raw_results.csv", rows)
    _write_csv(output_path / "paired_comparison.csv", pairs)
    _write_csv(output_path / "summary.csv", summary)
    (output_path / "analysis.md").write_text(_analysis(summary, pairs, scenario_records), encoding="utf-8")
    return {"scenarios": scenario_records, "rows": rows, "pairs": pairs, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="outputs/shared_comparison")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--start-seed", type=int, default=20260910)
    parser.add_argument("--active-only", action="store_true", help="only compare the two improved/active variants")
    args = parser.parse_args()
    run(args.output, args.trials, args.start_seed, include_baseline=not args.active_only)


if __name__ == "__main__":
    main()
