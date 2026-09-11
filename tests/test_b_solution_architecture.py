from b_solution import HTTPTransport, Session, Solver
from b_solution.core import Solver as CoreSolver
from b_solution.infrastructure import HTTPTransport as InfrastructureHTTPTransport


def test_public_api_uses_layered_implementations():
    assert Solver is CoreSolver
    assert HTTPTransport is InfrastructureHTTPTransport
    assert Session.__module__ == "b_solution.infrastructure.protocol"


def test_legacy_import_paths_remain_compatible():
    from b_solution.protocol import Session as LegacySession
    from b_solution.solver import Solver as LegacySolver

    assert LegacySession is Session
    assert LegacySolver is Solver
