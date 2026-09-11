"""Independent local emulator, NOT the official simulator or an official case.

The policy sees only request/response data. Truth is used exclusively by the
emulator and the evaluator after a run. This module does not read any official
simulator files or hidden official state.
"""
import hashlib
import math
import time
import numpy as np


class OfflineSimulator:
    def __init__(self, seed=0, mixed=False, radius_mode='random', error_mode='smooth', stress=False):
        rng = np.random.default_rng(seed)
        self.seed, self.error_mode = seed, error_mode
        count = int(rng.integers(10, 17))
        channels = rng.choice(np.arange(1, 21), count, replace=False)
        n_directional = int(rng.integers(1, count)) if mixed else 0
        self._sources = {}
        for i, ch in enumerate(channels):
            a = rng.uniform(0, 2 * np.pi)
            radius = 1800. if stress else 1800 * math.sqrt(rng.uniform())
            p = radius * np.array([math.cos(a), math.sin(a)])
            axis = (a if stress else rng.uniform(0, 2 * np.pi)) if i < n_directional else None
            self._sources[int(ch)] = {'position': p, 'radius': 1000. if radius_mode == 'min' else rng.uniform(1000, 1500),
                                     'axis': axis, 'cleared': False, 'phase': rng.uniform(0, 2 * np.pi, 2)}
        self.position, self.channel, self.vt = np.zeros(2), 1, 0.
        self.active, self.cache, self.path = False, {}, [[0., 0.]]
        self.checksum_initial = hashlib.sha256(repr([(ch, t['position'].tolist(), t['radius'], t['axis'])
                                                   for ch, t in self._sources.items()]).encode()).hexdigest()

    def error(self, p, ch, source):
        if self.error_mode == 'zero':
            return 0.
        if self.error_mode == 'smooth':
            f = source['phase']
            return math.sin(.017 * p[0] + f[0]) * math.cos(.013 * p[1] + f[1])
        h = hashlib.sha256(f'{self.seed}:{ch}:{p[0]:.8f}:{p[1]:.8f}'.encode()).digest()
        z = int.from_bytes(h[:8], 'little') / (2 ** 64 - 1)
        return (1. if z >= .5 else -1.) if self.error_mode == 'extreme' else 2 * z - 1

    def request(self, path, payload):
        key = payload['request_id']
        signature = (path, repr(payload))
        if key in self.cache:
            if self.cache[key][0] != signature:
                raise ValueError('Idempotency conflict')
            return self.cache[key][1].copy()
        response = {'accepted': True, 'real_timestamp_ms': int(time.time() * 1000)}
        if path == '/enter':
            if self.active:
                return {'accepted': False, 'virtual_time_s': 0, 'real_timestamp_ms': response['real_timestamp_ms']}
            self.active = True
            response.update(max_virtual_duration_s=360000, max_real_duration_s=1200, remaining_real_duration_s=1200)
        elif not self.active:
            raise RuntimeError('Inactive local test')
        elif path == '/exit':
            self.active = False
            response['exit_reason'] = 'user_exit'
        else:
            p = np.array([payload['position']['x'], payload['position']['y']], float)
            ch = payload['channel']
            # The official server accumulates microseconds. Round action cost
            # here to the nearest microsecond as a local approximation.
            move_time = float(np.linalg.norm(p - self.position) / 5)
            self.position = p
            self.path.append(p.tolist())
            source = self._sources.get(ch)
            d = float(np.linalg.norm(p - source['position'])) if source else math.inf
            live = source is not None and not source['cleared']
            if path == '/measure':
                self.vt += round(move_time + 5 + int(ch != self.channel), 6)
                self.channel = ch
                visible = live and d <= source['radius'] + 1e-9
                if visible and source['axis'] is not None:
                    u = np.array([math.cos(source['axis']), math.sin(source['axis'])])
                    visible = float((p - source['position']) @ u) >= -1e-9
                if not visible:
                    response['measure_result'] = 'no_signal'
                elif d <= 5:
                    response['measure_result'] = 'near'
                else:
                    v = source['position'] - p
                    bearing = math.degrees(math.atan2(v[1], v[0])) + self.error(p, ch, source)
                    response.update(measure_result='direction', svd_deg=round(bearing % 360, 2) % 360)
            elif path == '/clear':
                ok = live and d <= 20 + 1e-9
                self.vt += round(move_time + (5 if ok else 3), 6)
                response['clear_result'] = 'success' if ok else 'no_target_in_range'
                if ok:
                    source['cleared'] = True
            else:
                raise ValueError('Unknown command')
        response['virtual_time_s'] = round(self.vt, 6)
        self.cache[key] = (signature, response.copy())
        return response

    def evaluate(self):
        total = len(self._sources)
        cleared = sum(t['cleared'] for t in self._sources.values())
        return {'total': total, 'cleared_truth': cleared, 'clear_fraction': cleared / total,
                'directional': sum(t['axis'] is not None for t in self._sources.values()),
                'case_sha256': self.checksum_initial}

    def export_truth_for_local_plot(self):
        return [{'channel': ch, 'position': t['position'].tolist(), 'radius': t['radius'], 'axis': t['axis']}
                for ch, t in self._sources.items()]
