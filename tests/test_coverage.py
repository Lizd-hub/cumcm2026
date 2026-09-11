import numpy as np
from legacy_solution.common.coverage import coverage_grid,optical_grid
from legacy_solution.common.models import Observation
from legacy_solution.common.geometry import unit

def test_continuous_bound_constants():
    assert 600*np.sqrt(2)<1000
    assert 1500*np.sin(np.deg2rad(1.01))<40
    assert 10*np.sqrt(2)<20

def test_boundary_and_headings():
    angles=np.linspace(0,2*np.pi,360,endpoint=False)
    points=np.vstack([1800*np.column_stack([np.cos(angles),np.sin(angles)]),
                      [[-300,-300],[300,300],[0,0],[1800,0]]])
    omni=np.array(coverage_grid(3))
    mixed=np.array(coverage_grid(4))
    assert len(omni)==16 and len(mixed)==64
    for g in points:
        assert np.linalg.norm(omni-g,axis=1).min()<1000
        d=mixed-g
        close=np.linalg.norm(d,axis=1)<=1000
        for theta in angles:
            n=np.array([np.cos(theta),np.sin(theta)])
            assert np.any(close & (d@n>=-1e-8))

def test_optical_fallback_grid():
    o=Observation((100,-200),47)
    q=np.array(optical_grid(o))
    assert len(q)==380
    assert np.isclose(np.linalg.norm(np.diff(q,axis=0),axis=1).sum(),7580)
    rng=np.random.default_rng(22)
    for _ in range(500):
        distance=rng.uniform(5,1500)
        g=np.array(o.position)+distance*unit(o.bearing_deg+rng.uniform(-1.01,1.01))
        assert np.linalg.norm(q-g,axis=1).min()<20
