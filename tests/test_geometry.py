import itertools
import math
import numpy as np
import pytest
from common.geometry import (halfplane_region,enclosing_circle,circle_three,bearing_halfplanes,
                             disk_polygon,update_outer,disk_halfplanes)
from common.config import Config
from common.models import Observation
from solvers.problem1 import solve

def test_region_statuses():
    assert halfplane_region([[1,0],[-1,0]],[0,-1]).status=="empty"
    assert halfplane_region([[1,0]],[0]).status=="unbounded"
    assert halfplane_region([],[]).status=="unbounded"
    point=halfplane_region([[1,0],[-1,0],[0,1],[0,-1]],[2,-2,3,-3])
    assert point.diameter==pytest.approx(0)
    assert point.center==pytest.approx([2,3])
    line=halfplane_region([[1,0],[-1,0],[0,1],[0,-1]],[5,0,0,0])
    assert line.diameter==pytest.approx(5)

def test_cross_zero_and_forward_only():
    o=Observation((0,0),359.8)
    A,b=bearing_halfplanes(o,1.01)
    assert np.all(A@np.array([1000,0])<=b)
    assert not np.all(A@np.array([-1000,0])<=b)
    near=solve([{"position":[0,0],"bearing_deg":0},{"position":[0,1],"bearing_deg":.00001}])
    assert near["status"]=="unbounded"

def test_equilateral_counterexample():
    result=solve([])
    example=result["counterexample"]
    assert example["diameter"]==pytest.approx(100)
    assert example["radius"]==pytest.approx(100/math.sqrt(3))
    assert example["radius"]>example["diameter"]/2

def brute_circle(points):
    choices=[(p,0) for p in points]
    choices += [((a+b)/2,np.linalg.norm(a-b)/2) for a,b in itertools.combinations(points,2)]
    choices += [r for a,b,c in itertools.combinations(points,3) if (r:=circle_three(a,b,c)) is not None]
    return min(r for c,r in choices if np.all(np.linalg.norm(points-c,axis=1)<=r+1e-7))

@pytest.mark.parametrize("seed",range(20))
def test_circle_against_support_enumeration(seed):
    p=np.random.default_rng(seed).normal(size=(10,2))*100
    c,r=enclosing_circle(p)
    assert r==pytest.approx(brute_circle(p),rel=1e-8)
    assert np.all(np.linalg.norm(p-c,axis=1)<=r+1e-8)

def test_outer_contains_true_point():
    config=Config()
    g=np.array([1700.,200.])
    poly=disk_polygon((0,0),1800,128)
    for q,error in [([700,200],1),([1600,-200],-1),([1300,300],.99)]:
        delta=g-q
        theta=np.rad2deg(np.arctan2(delta[1],delta[0]))
        o=Observation(tuple(q),round((theta+error)%360,2)%360)
        A,b=bearing_halfplanes(o,config.delta_deg)
        assert np.all(A@g<=b+1e-6)
        poly=update_outer(poly,o,config)
        # 凸多边形每条有向边的叉积同号。
        edges=np.roll(poly,-1,axis=0)-poly
        cross=edges[:,0]*(g-poly)[:,1]-edges[:,1]*(g-poly)[:,0]
        assert np.all(cross>=-1e-5) or np.all(cross<=1e-5)
    a=np.linspace(0,2*np.pi,1000)
    boundary=1800*np.column_stack([np.cos(a),np.sin(a)])
    A,b=disk_halfplanes((0,0),1800)
    assert np.all(boundary@A.T<=b+1e-6)
