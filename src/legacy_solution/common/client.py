"""HTTP 协议及动作账本；同一时刻只允许一个动作。"""
import json
import math
import threading
import time
import unicodedata
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from legacy_solution.common.logging_io import serializable


class ProtocolError(RuntimeError):
    pass


class UncertainAction(ProtocolError):
    """请求可能已经执行，不能继续发送不同动作。"""


class BudgetExceeded(RuntimeError):
    pass


def validate_identifier(value, limit):
    if not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= limit:
        raise ValueError("invalid identifier length")
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in value):
        raise ValueError("identifier contains invisible characters")


class HttpTransport:
    def __init__(self, base_url="http://127.0.0.1:2026"):
        self.base_url = base_url.rstrip("/")

    def send(self, path, payload, timeout):
        request = Request(self.base_url+path, data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                          headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeError):
                body = {}
            return error.code, body


class Client:
    def __init__(self, transport, robot_id="offline", source="offline", journal=None):
        validate_identifier(robot_id,64)
        self.transport, self.robot_id, self.source = transport, robot_id, source
        self.position = (0.0,0.0)
        self.radio_channel = 1
        self.virtual_time_s = 0.0
        self.breakdown = dict(movement=0.0,measurement=0.0,switching=0.0,clear_success=0.0,clear_failure=0.0)
        self.events = []
        self.deadline = math.inf
        self.max_virtual = 360000.0
        self.entered = self.closed = self.uncertain = False
        self.start = None
        self.end = None
        self._lock = threading.Lock()
        self._cache = {}
        self._prefix = uuid.uuid4().hex
        self._counter = 0
        self.journal = Path(journal) if journal else None
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            # 原始动作日志不能覆盖。
            self.journal.open("x",encoding="utf-8").close()

    def _record(self, event):
        self.events.append(event)
        if self.journal:
            with self.journal.open("a",encoding="utf-8") as f:
                f.write(json.dumps(serializable(event),ensure_ascii=False,allow_nan=False)+"\n")

    def request(self, path, position=None, channel=None, request_id=None, phase="control"):
        if not self._lock.acquire(blocking=False):
            raise ProtocolError("concurrent action rejected")
        try:
            return self._request(path,position,channel,request_id,phase)
        finally:
            self._lock.release()

    def _request(self,path,position,channel,request_id,phase):
        if path not in ("/enter","/measure","/clear","/exit"):
            raise ValueError("invalid endpoint")
        self._counter += 1
        request_id = request_id or f"{self._prefix}-{self._counter}"
        validate_identifier(request_id,128)
        payload = dict(arena_id="default",robot_id=self.robot_id,request_id=request_id)
        if path in ("/measure","/clear"):
            if isinstance(channel,bool) or not isinstance(channel,int) or not 1 <= channel <= 20:
                raise ValueError("channel must be integer 1..20")
            if position is None or len(position) != 2 or any(not math.isfinite(float(x)) or abs(float(x)) > 2000000 for x in position):
                raise ValueError("invalid position")
            payload.update(position=dict(x=float(position[0]),y=float(position[1])),channel=channel)
        fingerprint = json.dumps([path,payload],sort_keys=True)
        if request_id in self._cache:
            old, body = self._cache[request_id]
            if old != fingerprint:
                raise ProtocolError("request_id reused with different action")
            return body
        if self.uncertain:
            raise UncertainAction("prior action unresolved")
        if self.closed:
            raise ProtocolError("session closed")
        if path != "/enter" and not self.entered:
            raise ProtocolError("enter required")
        if path == "/enter" and self.entered:
            raise ProtocolError("already entered")
        if self.entered and time.monotonic() >= self.deadline:
            raise BudgetExceeded("real deadline")
        before = dict(position=self.position,radio_channel=self.radio_channel,virtual_time_s=self.virtual_time_s)
        body = None
        for attempt in range(3):
            remaining = self.deadline-time.monotonic()
            if remaining <= 0:
                break
            try:
                status, body = self.transport.send(path,payload,min(3.0,remaining))
                self._record(dict(kind="attempt",path=path,request=payload,response=body,http_status=status,
                                  attempt=attempt+1,monotonic_s=time.monotonic(),phase=phase))
                if not isinstance(body,dict):
                    raise ValueError("response must be an object")
                if status in (429,500):
                    body = None
                elif status != 200:
                    raise ProtocolError(f"HTTP {status}")
                elif body.get("accepted") is not True:
                    raise ProtocolError("accepted=false; state unchanged")
                else:
                    break
            except (URLError,TimeoutError,ConnectionError,OSError,ValueError) as error:
                body = None
                self._record(dict(kind="network_error",path=path,request=payload,error=str(error),
                                  attempt=attempt+1,monotonic_s=time.monotonic(),phase=phase))
            if attempt < 2:
                delay = [0.2,0.5][attempt]
                if self.deadline-time.monotonic() <= delay:
                    break
                time.sleep(delay)
        if body is None:
            self.uncertain = True
            raise UncertainAction("retry budget exhausted; action outcome unknown")
        try:
            self._apply(path,payload,body)
        except (KeyError,TypeError,ValueError) as error:
            self.uncertain = True
            raise UncertainAction(f"malformed accepted response: {error}") from error
        self._cache[request_id] = (fingerprint,body)
        self._record(dict(kind="action",path=path,request=payload,response=body,before=before,
                          after=dict(position=self.position,radio_channel=self.radio_channel,
                                     virtual_time_s=self.virtual_time_s),
                          phase=phase,monotonic_s=time.monotonic()))
        return body

    def _apply(self,path,payload,body):
        virtual = float(body["virtual_time_s"])
        if not math.isfinite(virtual) or virtual < self.virtual_time_s:
            raise ValueError("invalid virtual clock")
        if path == "/enter":
            remaining = float(body["remaining_real_duration_s"])
            maximum = float(body["max_virtual_duration_s"])
            if not math.isfinite(remaining) or not 0 <= remaining <= 1200 or not math.isfinite(maximum) or maximum <= 0:
                raise ValueError("invalid budget")
            self.start = time.monotonic()
            self.deadline = self.start+remaining
            self.max_virtual = maximum
            self.entered = True
        elif path == "/exit":
            if body["exit_reason"] != "user_exit":
                raise ValueError("invalid exit reason")
            self.closed = True
            self.end = time.monotonic()
        else:
            q = (payload["position"]["x"],payload["position"]["y"])
            movement = math.dist(self.position,q)/5
            delta = dict.fromkeys(self.breakdown,0.0)
            delta["movement"] = movement
            if path == "/measure":
                result = body["measure_result"]
                if result not in ("direction","near","no_signal"):
                    raise ValueError("invalid measure_result")
                if result == "direction" and not 0 <= float(body["svd_deg"]) < 360:
                    raise ValueError("invalid bearing")
                delta["measurement"] = 5.0
                delta["switching"] = float(payload["channel"] != self.radio_channel)
            else:
                result = body["clear_result"]
                if result not in ("success","no_target_in_range"):
                    raise ValueError("invalid clear_result")
                delta["clear_success" if result == "success" else "clear_failure"] = 5.0 if result == "success" else 3.0
            expected = self.virtual_time_s+sum(delta.values())
            if abs(virtual-expected) > max(2e-5,1e-6*(len(self._cache)+1)):
                raise ValueError(f"virtual clock mismatch: {virtual} vs {expected}")
            for key,value in delta.items():
                self.breakdown[key] += value
            self.position = q
            if path == "/measure":
                self.radio_channel = payload["channel"]
        self.virtual_time_s = virtual

    @property
    def real_time_s(self):
        return 0.0 if self.start is None else (self.end or time.monotonic())-self.start

    def check_budget(self,position=None,action_cost=6.0,reserve=30.0):
        if time.monotonic()+reserve >= self.deadline:
            raise BudgetExceeded("real budget reserve")
        travel = 0.0 if position is None else math.dist(self.position,position)/5
        if self.virtual_time_s+travel+action_cost >= self.max_virtual:
            raise BudgetExceeded("virtual budget")
