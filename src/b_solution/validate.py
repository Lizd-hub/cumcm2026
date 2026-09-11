"""Backward-compatible entry point for :mod:`b_solution.cli.validate`."""

from .cli.validate import main, validate

__all__ = ["main", "validate"]

if __name__ == "__main__":
    main()
