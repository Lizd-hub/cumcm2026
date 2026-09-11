import copy
import pytest
from legacy_solution.common.client import Client,ProtocolError,UncertainAction
from legacy_solution.experiments.simulator import Simulator,Source

def test_annex_199_and_clear_does_not_switch():
    client=Client(Simulator([]))
    client.request("/enter")
    client.request("/measure",(300,400),1)
    client.request("/measure",(300,400),2)
    client.request("/clear",(300,0),3)
    assert client.radio_channel==2
    client.request("/measure",(300,0),2)
    client.request("/exit")
    assert client.virtual_time_s==199
    assert sum(client.breakdown.values())==199

def test_same_id_cache_and_conflict():
    client=Client(Simulator([]))
    client.request("/enter")
    response=client.request("/measure",(300,400),1,request_id="same")
    assert client.request("/measure",(300,400),1,request_id="same")==response
    assert client.virtual_time_s==105
    with pytest.raises(ProtocolError):
        client.request("/measure",(300,400),2,request_id="same")

def test_retry_after_committed_action_does_not_double_count():
    simulator=Simulator([])
    class Dropped:
        count=0
        requests=[]
        def send(self,path,payload,timeout):
            self.requests.append(copy.deepcopy(payload))
            response=simulator.send(path,payload,timeout)
            if path=="/measure" and self.count==0:
                self.count+=1
                raise ConnectionError("lost after commit")
            return response
    transport=Dropped()
    client=Client(transport)
    client.request("/enter")
    client.request("/measure",(300,400),1)
    assert client.virtual_time_s==105
    assert transport.requests[-1]==transport.requests[-2]

def test_rejected_zero_clock_does_not_reset_state():
    simulator=Simulator([])
    class Reject:
        reject=False
        def send(self,path,payload,timeout):
            return (200,dict(accepted=False,virtual_time_s=0)) if self.reject else simulator.send(path,payload,timeout)
    transport=Reject()
    client=Client(transport)
    client.request("/enter")
    client.request("/measure",(300,400),2)
    transport.reject=True
    with pytest.raises(ProtocolError):
        client.request("/clear",(0,0),3)
    assert client.position==(300,400)
    assert client.radio_channel==2
    assert client.virtual_time_s==106

def test_near_and_fixed_error_and_directional_backside():
    simulator=Simulator([Source(1,(100,0),1000,0)])
    client=Client(simulator)
    client.request("/enter")
    assert client.request("/measure",(0,0),1)["measure_result"]=="no_signal"
    a=client.request("/measure",(300,100),1)
    b=client.request("/measure",(300,100),1)
    assert a["svd_deg"]==b["svd_deg"]
    assert client.request("/measure",(100,0),1)["measure_result"]=="near"
    assert client.request("/clear",(99,0),1)["clear_result"]=="success"
    assert client.request("/clear",(99,0),1)["clear_result"]=="no_target_in_range"

def test_uncertain_stops_future_actions(monkeypatch):
    simulator=Simulator([])
    class Drop:
        def send(self,path,payload,timeout):
            if path=="/enter":
                return simulator.send(path,payload,timeout)
            raise ConnectionError("offline")
    monkeypatch.setattr("legacy_solution.common.client.time.sleep",lambda _:None)
    client=Client(Drop())
    client.request("/enter")
    with pytest.raises(UncertainAction):
        client.request("/measure",(0,0),1)
    with pytest.raises(UncertainAction):
        client.request("/exit")
    assert client.virtual_time_s==0

@pytest.mark.parametrize("channel",[0,21,True,1.5])
def test_invalid_channel(channel):
    client=Client(Simulator([]))
    client.request("/enter")
    with pytest.raises(ValueError):
        client.request("/measure",(0,0),channel)

def test_http_transport_serializes_protocol(monkeypatch):
    import json
    from legacy_solution.common.client import HttpTransport
    captured = {}
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
        def read(self):
            return b'{"accepted":true,"virtual_time_s":0}'
    def fake_open(request,timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()
    monkeypatch.setattr("legacy_solution.common.client.urlopen",fake_open)
    payload = {"arena_id":"default","robot_id":"example","request_id":"1"}
    status,body = HttpTransport().send("/enter",payload,3)
    assert status == 200 and body["accepted"]
    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:2026/enter"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data.decode("utf-8")) == payload
