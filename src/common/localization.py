"""候选评分是启发式，安全标签只依据完整凸外包络。"""
import time
import numpy as np
from common.geometry import unit, enclosing_circle, clip, bearing_halfplanes
from common.models import Observation

def scenarios(poly, exclusions, limit):
    p = np.asarray(poly)
    center = p.mean(axis=0)
    samples = [*p, *((p+np.roll(p, -1, axis=0))/2)]
    for i in range(limit):
        t = (i+0.5)/limit
        samples.append((1-t)*center+t*(0.381966*p[i%len(p)]+0.618034*p[(i+1)%len(p)]))
    samples = np.asarray(samples)
    for origin, radius in exclusions:
        samples = samples[np.linalg.norm(samples-origin, axis=1) > radius]
    return samples

def choose_next(position, radio_channel, target, config, mixed=False, next_node=None, deadline=None):
    poly = np.asarray(target.outer)
    if len(poly) == 0 or not target.observations:
        return None
    center, radius = enclosing_circle(poly)
    first = target.observations[0]
    reference = first.position if len(target.observations) == 1 else position
    e = unit(first.bearing_deg) if len(target.observations) == 1 else center-np.asarray(position)
    if np.linalg.norm(e) < 1e-9:
        e = unit(first.bearing_deg)
    e = e/np.linalg.norm(e)
    ep = np.array([-e[1], e[0]])
    candidates = [np.asarray(reference)+a*e+b*ep for a in [0,100,250,500,750]
                  for b in [-400,-200,-100,-50,50,100,200,400]]
    candidates.append(center)
    if next_node is not None:
        candidates.append(np.asarray(next_node))
    history = np.array([o.position for o in target.observations])
    candidates = [q for q in candidates if np.linalg.norm(q) <= 3300
                  and np.min(np.linalg.norm(history-q, axis=1)) >= 10 and np.linalg.norm(q-position) >= 10]
    G = scenarios(poly, target.exclusions, config.scenario_limit)
    for observation in target.observations:
        G = G[np.linalg.norm(G-observation.position, axis=1) > 5]
    if not candidates or len(G) == 0:
        return None
    records = []
    for q in candidates:
        distances = np.linalg.norm(G-q, axis=1)
        u, v = G-first.position, G-q
        denominator = np.linalg.norm(u, axis=1)*np.linalg.norm(v, axis=1)
        gamma = np.divide(np.abs(u[:,0]*v[:,1]-u[:,1]*v[:,0]), denominator,
                          out=np.zeros_like(denominator), where=denominator > 1e-9)
        safe = bool(np.max(np.linalg.norm(poly-q, axis=1)) <= 1000)
        move = float(np.linalg.norm(q-position)/5)
        recv = float(np.mean(distances <= 1000))
        proxy = move+5+(target.channel != radio_channel)+2*radius/(5*(1+5*float(np.mean(gamma))))+60*(1-recv)
        records.append(dict(point=q.tolist(), distance_safe=safe, guaranteed_reception=safe and not mixed,
                            movement_s=move, min_gamma=float(gamma.min()), receive_scenario_fraction=recv,
                            preliminary_score_s=proxy, score_s=None, posterior_radius_estimate=None))
    pool = [r for r in records if r["distance_safe"]] or records
    shortlist = sorted(pool, key=lambda r: (r["preliminary_score_s"], r["point"]))[:config.candidate_shortlist]
    evaluated = []
    for record in shortlist:
        q = np.asarray(record["point"])
        worst, finished = 0.0, True
        for g in G:
            if deadline is not None and time.monotonic() >= deadline:
                finished = False
                break
            if np.linalg.norm(g-q) <= 5:
                worst = max(worst, 5)
                continue
            theta = np.rad2deg(np.arctan2(*(g-q)[::-1]))
            for error in [-config.delta_deg, 0, config.delta_deg]:
                posterior = clip(poly, *bearing_halfplanes(Observation(tuple(q), theta+error), config.delta_deg))
                if len(posterior):
                    _, r = enclosing_circle(posterior)
                    worst = max(worst, r)
        if not finished:
            break
        score = record["movement_s"]+5+(target.channel != radio_channel)+2*worst/5+60*(1-record["receive_scenario_fraction"])
        record.update(score_s=float(score), posterior_radius_estimate=float(worst))
        evaluated.append(record)
    chosen = min(evaluated or shortlist, key=lambda r: (
        r["score_s"] if r["score_s"] is not None else r["preliminary_score_s"],
        r["movement_s"], -r["min_gamma"], r["point"]))
    return dict(selected=chosen["point"], candidates=records, scenario_count=len(G),
                shortlist_count=len(shortlist), evaluated_count=len(evaluated),
                safe_region_definition="max_vertex_distance(q, outer) <= 1000",
                guarantee="distance_only" if mixed else "omnidirectional_reception",
                scoring_note="离散场景评分不是连续极大值或接收概率", outer=poly.tolist())
