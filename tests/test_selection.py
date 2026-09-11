import numpy as np
from legacy_solution.common.models import Observation,ChannelState
from legacy_solution.common.config import Config
from legacy_solution.common.geometry import disk_polygon,update_outer
from legacy_solution.common.localization import choose_next

def test_guarantee_and_determinism():
    config=Config(scenario_limit=8,candidate_shortlist=2)
    o=Observation((0,0),35)
    poly=update_outer(disk_polygon((0,0),1800),o,config)
    target=ChannelState(1,"detected",[o],poly.tolist())
    a=choose_next((0,0),1,target,config)
    b=choose_next((0,0),1,target,config)
    assert a["selected"]==b["selected"]
    for c in a["candidates"]:
        expected=np.linalg.norm(poly-c["point"],axis=1).max()<=1000
        assert c["guaranteed_reception"]==expected
    mixed=choose_next((0,0),1,target,config,mixed=True)
    assert not any(c["guaranteed_reception"] for c in mixed["candidates"])
