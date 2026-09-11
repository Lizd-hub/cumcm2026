"""主解题方案（v0.2.0）。

The package contains the improved solver selected after the shared offline
comparison.  It is intentionally independent of the legacy implementation.
"""

__version__ = "0.2.0"

from .protocol import HTTPTransport, Session
from .solver import Solver, Target, coverage_sites

__all__ = ["HTTPTransport", "Session", "Solver", "Target", "coverage_sites"]
