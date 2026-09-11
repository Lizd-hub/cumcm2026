from dataclasses import replace
import pytest
from legacy_solution.common.client import Client
from legacy_solution.common.config import Config
from legacy_solution.experiments.simulator import random_scene,Simulator,Source
from legacy_solution.solvers import problem3,problem4

@pytest.mark.parametrize("problem",[3,4])
@pytest.mark.parametrize("count",[10,11,16])
def test_full_completion(problem,count):
    simulator=random_scene(2026+count,problem,count)
    solver=problem3 if problem==3 else problem4
    result=solver.solve(Client(simulator),Config(baseline=True))
    assert result.complete
    assert result.cleared_count==count
    assert simulator.evaluate()["true_cleared_count"]==count
    if count<16:
        assert all(c["status"] in ("cleared","absent_certified") for c in result.channels)

def test_budget_is_incomplete_and_exits():
    simulator=Simulator([Source(1,(1500,0))],real_budget=1)
    client=Client(simulator)
    result=problem3.solve(client)
    assert not result.complete
    assert "BudgetExceeded" in result.reason
    assert client.closed

def test_mixed_negative_does_not_create_distance_exclusion():
    simulator=random_scene(31,4,10)
    result=problem4.solve(Client(simulator),Config(baseline=True))
    assert all(radius!=1000 for t in result.channels for _,radius in t["exclusions"])

def test_solver_does_not_require_truth_interface():
    simulator=random_scene(33,3,10)
    class OnlySend:
        def send(self,*args,**kwargs):
            return simulator.send(*args,**kwargs)
    result=problem3.solve(Client(OnlySend()),Config(baseline=True))
    assert result.complete
