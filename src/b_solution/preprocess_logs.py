"""Backward-compatible entry point for :mod:`b_solution.cli.preprocess_logs`."""

from .cli.preprocess_logs import audit, main

__all__ = ["audit", "main"]

if __name__ == "__main__":
    main()
