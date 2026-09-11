from dataclasses import dataclass, field
from typing import Literal

Point = tuple[float, float]


@dataclass(frozen=True)
class Observation:
    position: Point
    bearing_deg: float


@dataclass
class GeometryResult:
    status: Literal["empty", "unbounded", "bounded"]
    vertices: list
    diameter: float | None = None
    farthest_pair: list | None = None
    center: list | None = None
    radius: float | None = None


@dataclass
class ChannelState:
    channel: int
    status: str = "unknown"
    observations: list[Observation] = field(default_factory=list)
    outer: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    negative_nodes: set = field(default_factory=set)
    near_position: Point | None = None


@dataclass
class RunResult:
    problem: int
    source: str
    complete: bool
    reason: str
    cleared_count: int
    virtual_time_s: float
    real_time_s: float
    time_breakdown: dict
    channels: list
    events: list
    config: dict
    coverage: list
    seed: int | None = None
    true_count: int | None = None
    cleared_fraction: float | None = None
    average_time_s: float | None = None
