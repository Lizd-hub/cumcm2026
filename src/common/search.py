"""共享搜索引擎，仅接收客户端反馈，不读取模拟器目标真值。"""
from dataclasses import asdict
import math
import time
import numpy as np
from common.config import Config
from common.models import ChannelState, Observation, RunResult
from common.geometry import disk_polygon, update_outer, enclosing_circle
from common.coverage import coverage_grid, optical_grid
from common.localization import choose_next
from common.client import ProtocolError, BudgetExceeded


def solve_search(problem,client,config=None):
    config = config or Config()
    grid = coverage_grid(problem)
    channels = [ChannelState(i) for i in range(1,21)]
    issues = []

    def clear(target,q,phase):
        client.check_budget(q,5,config.reserve_seconds)
        body = client.request("/clear",q,target.channel,phase=phase)
        if body["clear_result"] == "success":
            target.status = "cleared"
            return True
        target.exclusions.append((list(q),20))
        target.near_position = None
        return False

    def measure(target,q,phase,node=None):
        client.check_budget(q,6,config.reserve_seconds)
        body = client.request("/measure",q,target.channel,phase=phase)
        result = body["measure_result"]
        if result == "direction":
            target.status = "detected"
            o = Observation(tuple(q),body["svd_deg"])
            target.observations.append(o)
            poly = target.outer if len(target.outer) else disk_polygon((0,0),1800,config.disk_sides)
            target.outer = update_outer(poly,o,config).tolist()
            if not target.outer:
                issues.append(f"channel {target.channel}: inconsistent geometric region; using original bearing fallback")
        elif result == "near":
            target.status = "detected"
            target.near_position = tuple(q)
            if not clear(target,q,"clear"):
                raise ProtocolError("near followed by failed clear")
        else:
            if node is not None and target.status == "unknown":
                target.negative_nodes.add(node)
            if problem == 3:
                target.exclusions.append((list(q),1000))
        return result

    def resolve(target,next_node):
        extra = consecutive = 0
        forced_fallback = config.baseline
        while target.status != "cleared":
            client.check_budget(reserve=config.reserve_seconds)
            if target.outer and not forced_fallback:
                center,radius = enclosing_circle(target.outer)
                if radius <= config.clear_radius:
                    if clear(target,center,"clear"):
                        return
                    issues.append(f"channel {target.channel}: guaranteed circle clear failed")
                    forced_fallback = True
            if forced_fallback or not target.outer or extra >= config.max_local_measures or consecutive >= config.max_no_signal:
                if not target.observations:
                    raise ProtocolError("detected target has no bearing for fallback")
                for q in optical_grid(target.observations[0]):
                    if clear(target,q,"fallback"):
                        return
                raise ProtocolError("finite fallback exhausted without success")
            deadline = min(client.deadline-config.reserve_seconds,time.monotonic()+0.2) if client.source != "offline" else None
            choice = choose_next(client.position,client.radio_channel,target,config,problem == 4,next_node,deadline)
            if choice is None:
                forced_fallback = True
                continue
            result = measure(target,choice["selected"],"localization")
            extra += 1
            consecutive = consecutive+1 if result == "no_signal" else 0

    def complete():
        return sum(t.status == "cleared" for t in channels) == 16 or all(
            t.status in ("cleared","absent_certified") for t in channels)

    reason = "coverage_incomplete"
    try:
        client.request("/enter")
        for node,q in [(-1,(0,0)),*enumerate(grid)]:
            unknown = [t for t in channels if t.status == "unknown"]
            unknown.sort(key=lambda t:(t.channel != client.radio_channel,t.channel))
            for target in unknown:
                measure(target,q,"coverage",None if node < 0 else node)
            for target in channels:
                if target.status == "unknown" and len(target.negative_nodes) == len(grid):
                    target.status = "absent_certified"
            while any(t.status == "detected" for t in channels):
                pending = [t for t in channels if t.status == "detected"]
                def priority(t):
                    if not t.outer:
                        return (math.inf,t.channel != client.radio_channel,t.channel)
                    c,r = enclosing_circle(t.outer)
                    cost = math.dist(client.position,c)/5+5+6*math.ceil(math.log2(max(1,r/config.clear_radius)))
                    return (cost,t.channel != client.radio_channel,t.channel)
                target = min(pending,key=priority)
                next_node = grid[node+1] if node+1 < len(grid) else None
                resolve(target,next_node)
            if complete():
                reason = "cleared_upper_bound" if sum(t.status == "cleared" for t in channels) == 16 else "channel_coverage_certificate"
                break
    except (ProtocolError,BudgetExceeded,ArithmeticError,ValueError) as error:
        reason = f"{type(error).__name__}: {error}"
    finally:
        if client.entered and not client.closed and not client.uncertain and time.monotonic() < client.deadline:
            try:
                client.request("/exit")
            except (ProtocolError,BudgetExceeded) as error:
                issues.append(f"exit: {error}")
    count = sum(t.status == "cleared" for t in channels)
    if issues:
        reason += "; " + "; ".join(issues)
    return RunResult(problem,client.source,complete(),reason,count,client.virtual_time_s,client.real_time_s,
                     dict(client.breakdown),[asdict(t) for t in channels],client.events,asdict(config),grid,
                     average_time_s=client.virtual_time_s/count if count else None)
