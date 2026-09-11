"""Unified command-line interface for the B-problem solution."""

from __future__ import annotations

import argparse
import importlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m b_solution")
    modules = {
        "run": "b_solution.cli.run",
        "benchmark": "b_solution.cli.benchmark",
        "validate": "b_solution.cli.validate",
        "preprocess": "b_solution.cli.preprocess_logs",
        "figures": "b_solution.reporting.make_figures",
        "report": "b_solution.reporting.build_report",
    }
    parser.add_argument("command", choices=modules, help="subcommand to execute")
    if len(sys.argv) == 1 or sys.argv[1] in {"-h", "--help"}:
        parser.print_help()
        return
    command = sys.argv[1]
    if command not in modules:
        parser.error(f"unknown command: {command}")
    sys.argv = [f"{parser.prog} {command}", *sys.argv[2:]]
    importlib.import_module(modules[command]).main()


if __name__ == "__main__":
    main()
