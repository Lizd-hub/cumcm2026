"""Shared offline environment for comparing the two independent solutions.

The purpose of this module is experimental fairness, not official-simulator
emulation. A :class:`Scenario` is generated once and the same source truth,
measurement error field and action-cost rules are used for both solvers. Each
solver receives a fresh stateful transport, so one run cannot affect another.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import math
import time

import numpy as np


@dataclass(frozen=True)
class SharedSource:
    channel: int
    position: tuple[float, float]
    radius: float = 1000.0
    heading_deg: float | None = None


@dataclass(frozen=True)
class Scenario:
    problem: int
    seed: int
    profile: str
    sources: tuple[SharedSource, ...]

    def as_dict(self) -> dict:
        return {
            "problem": self.problem,
            "seed": self.seed,
            "profile": self.profile,
            "sources": [asdict(source) for source in self.sources],
        }


def make_scenario(problem: int, seed: int, profile: str = "random", count: int | None = None) -> Scenario:
    """Create a deterministic case shared by both solution implementations.

    ``random`` uses area-uniform source positions and mixed receive radii.
    ``boundary`` places every source on the 1800 m boundary with the minimum
    receive radius; Q4 additionally makes every source directional and points
    each emission axis radially outward. The latter is a deliberately hard,
    reproducible stress profile.
    """

    if problem not in (3, 4):
        raise ValueError("problem must be 3 or 4")
    if profile not in ("random", "boundary"):
        raise ValueError("profile must be random or boundary")
    rng = np.random.default_rng(seed)
    source_count = count if count is not None else int(rng.integers(10, 17))
    if not 1 <= source_count <= 16:
        raise ValueError("count must be between 1 and 16")
    channels = rng.choice(np.arange(1, 21), source_count, replace=False)
    sources: list[SharedSource] = []
    for index, channel in enumerate(channels):
        angle = float(rng.uniform(0, 2 * np.pi))
        if profile == "boundary":
            radius_from_origin = 1800.0
            receive_radius = 1000.0
        else:
            radius_from_origin = 1800.0 if index == 0 else 1800.0 * math.sqrt(float(rng.random()))
            receive_radius = 1000.0 if index == 0 else float(rng.uniform(1000, 1500))
        position = (radius_from_origin * math.cos(angle), radius_from_origin * math.sin(angle))
        if problem == 3:
            heading = None
        elif profile == "boundary":
            heading = float(math.degrees(angle) % 360)
        elif index == 0:
            heading = float(math.degrees(angle) % 360)
        elif index % 2 == 0:
            heading = float(rng.uniform(0, 360))
        else:
            heading = None
        sources.append(SharedSource(int(channel), position, receive_radius, heading))
    return Scenario(problem, seed, profile, tuple(sources))


class SharedSimulator:
    """A transport implementing both ``Client`` and ``Session`` protocols."""

    def __init__(self, scenario: Scenario, real_budget: float = 1200.0):
        self.scenario = scenario
        self._sources = {source.channel: source for source in scenario.sources}
        self._cleared: set[int] = set()
        self._cache: dict[str, tuple[str, dict]] = {}
        self._position = (0.0, 0.0)
        self._channel = 1
        self._virtual = 0.0
        self._entered = False
        self._closed = False
        self.real_budget = real_budget
        self.path: list[list[float]] = [[0.0, 0.0]]

    @staticmethod
    def _response(accepted: bool, virtual_time_s: float, **extra) -> dict:
        response = {
            "accepted": accepted,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(virtual_time_s, 6) if accepted else 0,
        }
        response.update(extra)
        return response

    def _error(self, channel: int, point: tuple[float, float]) -> float:
        """A fixed, bounded error field shared by all runs of this case."""

        raw = f"{self.scenario.seed}:{channel}:{point[0]:.8f}:{point[1]:.8f}".encode()
        value = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
        return 2 * value / (2**64 - 1) - 1

    def _fingerprint(self, path: str, payload: dict) -> str:
        return json.dumps([path, payload], sort_keys=True, separators=(",", ":"))

    def _process(self, path: str, payload: dict) -> dict:
        if path not in ("/enter", "/measure", "/clear", "/exit"):
            return self._response(False, self._virtual)
        expected = {"arena_id", "robot_id", "request_id"}
        if path in ("/measure", "/clear"):
            expected |= {"position", "channel"}
        if set(payload) != expected or payload.get("arena_id") != "default":
            return self._response(False, self._virtual)
        if self._closed or (path != "/enter" and not self._entered):
            return self._response(False, self._virtual)
        if path == "/enter":
            if self._entered:
                return self._response(False, self._virtual)
            self._entered = True
            return self._response(
                True,
                self._virtual,
                max_virtual_duration_s=360000,
                max_real_duration_s=1200,
                remaining_real_duration_s=self.real_budget,
            )
        if path == "/exit":
            self._closed = True
            return self._response(True, self._virtual, exit_reason="user_exit")

        point = (float(payload["position"]["x"]), float(payload["position"]["y"]))
        channel = int(payload["channel"])
        self._virtual += math.dist(point, self._position) / 5
        self._position = point
        self.path.append([point[0], point[1]])
        source = self._sources.get(channel)
        if channel in self._cleared:
            source = None
        distance = math.dist(point, source.position) if source else math.inf
        if path == "/clear":
            success = distance <= 20.0 + 1e-9
            self._virtual += 5.0 if success else 3.0
            if success:
                self._cleared.add(channel)
            return self._response(True, self._virtual, clear_result="success" if success else "no_target_in_range")

        self._virtual += 5.0 + float(channel != self._channel)
        self._channel = channel
        visible = source is not None and distance <= source.radius + 1e-9
        if visible and source.heading_deg is not None:
            axis = math.radians(source.heading_deg)
            visible = math.cos(axis) * (point[0] - source.position[0]) + math.sin(axis) * (
                point[1] - source.position[1]
            ) >= -1e-9
        if not visible:
            return self._response(True, self._virtual, measure_result="no_signal")
        if distance <= 5.0:
            return self._response(True, self._virtual, measure_result="near")
        theta = math.degrees(math.atan2(source.position[1] - point[1], source.position[0] - point[0]))
        bearing = round((theta + self._error(channel, point)) % 360, 2) % 360
        return self._response(True, self._virtual, measure_result="direction", svd_deg=bearing)

    def send(self, path: str, payload: dict, timeout: float = 3.0) -> tuple[int, dict]:
        """Transport method used by ``src.common.client.Client``."""

        del timeout
        key = payload.get("request_id")
        fingerprint = self._fingerprint(path, payload)
        if key in self._cache:
            old, response = self._cache[key]
            return (200, copy.deepcopy(response)) if old == fingerprint else (409, self._response(False, self._virtual))
        response = self._process(path, payload)
        self._cache[key] = (fingerprint, copy.deepcopy(response))
        return 200, response

    def request(self, path: str, payload: dict) -> dict:
        """Transport method used by ``b_solution.protocol.Session``."""

        status, response = self.send(path, payload)
        if status != 200:
            raise RuntimeError(f"shared simulator returned HTTP {status}")
        return response

    def evaluate(self) -> dict:
        truth = [asdict(source) for source in self.scenario.sources]
        digest = hashlib.sha256(json.dumps(truth, sort_keys=True).encode()).hexdigest()
        return {
            "true_count": len(self._sources),
            "true_cleared_count": len(self._cleared),
            "truth": truth,
            "case_sha256": digest,
        }

