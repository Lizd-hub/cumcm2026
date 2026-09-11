"""主解题方案（v0.3.0）。

The package contains the improved solver selected after the shared offline
comparison.  It is intentionally independent of the legacy implementation.
"""

__version__ = "0.3.0"

from .infrastructure.protocol import HTTPTransport, Session
from .core.solver import Solver, Target, coverage_sites

__all__ = ["HTTPTransport", "Session", "Solver", "Target", "coverage_sites"]
