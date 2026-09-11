"""自建离线场景，不声称复现官方误差场或官方成绩。"""
from dataclasses import dataclass
import copy
import hashlib
import json
import math
import time
import numpy as np


@dataclass(frozen=True)
class Source:
    channel: int
    position: tuple
    radius: float = 1000.0
    heading_deg: float | None = None


class Simulator:
    def __init__(self,sources,seed=20260910,real_budget=1200):
        if len({s.channel for s in sources}) != len(sources):
            raise ValueError("duplicate channels")
        for s in sources:
            if not 1 <= s.channel <= 20 or math.hypot(*s.position) > 1800+1e-6 or not 1000 <= s.radius <= 1500:
                raise ValueError("invalid source")
        self._sources = {s.channel:s for s in sources}
        self._cleared = set()
        self._seed = seed
        self._cache = {}
        self._position = (0,0)
        self._channel = 1
        self._virtual = 0.0
        self._entered = self._closed = False
        self.real_budget = real_budget

    def _response(self,accepted,**kwargs):
        return dict(accepted=accepted,real_timestamp_ms=int(time.time()*1000),
                    virtual_time_s=round(self._virtual,6) if accepted else 0,**kwargs)

    def send(self,path,payload,timeout=3):
        key = payload.get("request_id")
        fingerprint = json.dumps([path,payload],sort_keys=True)
        if key in self._cache:
            old,response = self._cache[key]
            return (200,copy.deepcopy(response)) if old == fingerprint else (409,self._response(False))
        expected = {"arena_id","robot_id","request_id"} | ({"position","channel"} if path in ("/measure","/clear") else set())
        if set(payload) != expected or payload.get("arena_id") != "default":
            return 200,self._response(False)
        if self._closed or (path != "/enter" and not self._entered):
            return 200,self._response(False)
        if path == "/enter":
            if self._entered:
                return 200,self._response(False)
            self._entered = True
            response = self._response(True,max_virtual_duration_s=360000,max_real_duration_s=1200,
                                      remaining_real_duration_s=self.real_budget)
        elif path == "/exit":
            self._closed = True
            response = self._response(True,exit_reason="user_exit")
        elif path in ("/measure","/clear"):
            q = (payload["position"]["x"],payload["position"]["y"])
            channel = payload["channel"]
            self._virtual += math.dist(q,self._position)/5
            self._position = q
            source = self._sources.get(channel) if channel not in self._cleared else None
            distance = math.dist(q,source.position) if source else math.inf
            if path == "/clear":
                success = distance <= 20
                if success:
                    self._cleared.add(channel)
                self._virtual += 5 if success else 3
                response = self._response(True,clear_result="success" if success else "no_target_in_range")
            else:
                self._virtual += 5+(channel != self._channel)
                self._channel = channel
                visible = source is not None and distance <= source.radius
                if visible and source.heading_deg is not None:
                    a = math.radians(source.heading_deg)
                    visible = math.cos(a)*(q[0]-source.position[0])+math.sin(a)*(q[1]-source.position[1]) >= -1e-9
                if not visible:
                    response = self._response(True,measure_result="no_signal")
                elif distance <= 5:
                    response = self._response(True,measure_result="near")
                else:
                    theta = math.degrees(math.atan2(source.position[1]-q[1],source.position[0]-q[0]))
                    # 精确位置和频道的固定哈希误差，重复测量不会重新抽样。
                    key_bytes = repr((self._seed,channel,float(q[0]),float(q[1]))).encode()
                    n = int.from_bytes(hashlib.sha256(key_bytes).digest()[:8],"big")
                    error = 2*n/(2**64-1)-1
                    response = self._response(True,measure_result="direction",svd_deg=round((theta+error)%360,2)%360)
        else:
            return 404,self._response(False)
        self._cache[key] = (fingerprint,copy.deepcopy(response))
        return 200,response

    def evaluate(self):
        return dict(true_count=len(self._sources),true_cleared_count=len(self._cleared),
                    truth=[dict(channel=s.channel,position=s.position,radius=s.radius,heading_deg=s.heading_deg)
                           for s in self._sources.values()])


def random_scene(seed,problem,count=None):
    rng = np.random.default_rng(seed)
    count = count if count is not None else int(rng.integers(10,17))
    channels = rng.choice(np.arange(1,21),count,replace=False)
    sources = []
    for i,channel in enumerate(channels):
        theta = rng.uniform(0,2*np.pi)
        r = 1800 if i == 0 else 1800*np.sqrt(rng.random())
        heading = float(np.rad2deg(theta)%360) if problem == 4 and i == 0 else (
            float(rng.uniform(0,360)) if problem == 4 and i%2 == 0 else None)
        sources.append(Source(int(channel),(float(r*np.cos(theta)),float(r*np.sin(theta))),
                              1000.0 if i == 0 else float(rng.uniform(1000,1500)),heading))
    return Simulator(sources,seed)
